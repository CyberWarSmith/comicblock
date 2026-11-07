"""
comicblock bridge - lets comicblock (and Claude Code, through tools/blender_mcp_server.py) drive the
Blender session you have open, so you can watch sets build and panels stage, and adjust them by hand.

Opens a loopback socket that accepts Python and runs it inside the live Blender session.
Without it, comicblock runs Blender headless in the background (the default).

TWO WAYS TO RUN
  Quickest:  open this file in Blender's Text Editor and press Alt+P. The server
             starts immediately and stays up until you quit Blender or press the
             Stop button in View3D > Sidebar (N) > comicblock.
  Add-on:    Edit > Preferences > Add-ons > Install from Disk, pick this file,
             enable it, then Start Server from that same sidebar panel.

THREADING
  Blender's API is not thread safe. The socket runs on a background thread and does
  no bpy work at all; it parks each request on a queue, and a main-thread timer
  drains that queue, executes, and hands the result back. Ignoring this is the usual
  reason ad-hoc Blender socket servers crash the app.

SCOPE
  Binds to 127.0.0.1 only. Anything that can reach that port can run Python as you,
  so stop the server when you are not using it.
"""

bl_info = {
    "name": "comicblock Bridge",
    "author": "comicblock contributors",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar (N) > comicblock",
    "description": "Loopback socket that executes Python in the running session.",
    "category": "Development",
}

import bpy
import json
import queue
import socket
import threading
import traceback
import io
import contextlib
import os

HOST = "127.0.0.1"
PORT = int(os.environ.get("COMICBLOCK_BRIDGE_PORT", "9876"))

_requests = queue.Queue()
_server = None


class _Request:
    __slots__ = ("payload", "done", "reply")

    def __init__(self, payload):
        self.payload = payload
        self.done = threading.Event()
        self.reply = None


# ------------------------------------------------------------------ main thread

def _run_code(code):
    """Execute in a namespace holding bpy. Returns stdout plus an optional `result`."""
    ns = {"bpy": bpy, "__name__": "__comicblock_bridge__"}
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(code, ns)
    except (Exception, SystemExit):                  # SystemExit too: it must not escape into Blender's timer
        return {"ok": False, "stdout": out.getvalue(), "error": traceback.format_exc()}
    reply = {"ok": True, "stdout": out.getvalue()}
    if "result" in ns:
        try:
            reply["result"] = repr(ns["result"])
        except Exception as exc:
            reply["result"] = "<unrepr-able: {}>".format(exc)
    return reply


def _scene_info():
    scene = bpy.context.scene
    objects = []
    for obj in scene.objects:
        entry = {"name": obj.name, "type": obj.type}
        if obj.type == "MESH" and obj.data:
            entry["verts"] = len(obj.data.vertices)
            entry["polys"] = len(obj.data.polygons)
        if obj.modifiers:
            entry["modifiers"] = [m.type for m in obj.modifiers]
        objects.append(entry)
    return {
        "ok": True,
        "blender": bpy.app.version_string,
        "file": bpy.data.filepath or "<unsaved>",
        "scene": scene.name,
        "engine": scene.render.engine,
        "frame": scene.frame_current,
        "collections": [c.name for c in bpy.data.collections],
        "object_count": len(objects),
        "objects": objects[:200],
    }


def _drain():
    """Main-thread pump. Registered as a Blender timer."""
    while True:
        try:
            req = _requests.get_nowait()
        except queue.Empty:
            break
        try:
            cmd = req.payload.get("cmd", "exec")
            if cmd == "exec":
                req.reply = _run_code(req.payload.get("code", ""))
            elif cmd == "scene_info":
                req.reply = _scene_info()
            elif cmd == "ping":
                req.reply = {"ok": True, "blender": bpy.app.version_string}
            else:
                req.reply = {"ok": False, "error": "unknown cmd: " + str(cmd)}
        except Exception:
            req.reply = {"ok": False, "error": traceback.format_exc()}
        finally:
            req.done.set()
    return 0.05


# ------------------------------------------------------------- socket thread

class BridgeServer:
    def __init__(self, host=HOST, port=PORT):
        self.host, self.port = host, port
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        self._stop.clear()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(4)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        if not bpy.app.timers.is_registered(_drain):
            bpy.app.timers.register(_drain, persistent=True)
        print("[comicblock bridge] listening on {}:{}".format(self.host, self.port))

    def stop(self):
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if bpy.app.timers.is_registered(_drain):
            try:
                bpy.app.timers.unregister(_drain)
            except Exception:
                pass
        print("[comicblock bridge] stopped")

    def _serve(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            conn.settimeout(900.0)
            chunks = []
            while True:
                data = conn.recv(65536)
                if not data:
                    break
                chunks.append(data)
                # Requests are newline-terminated JSON.
                if data.endswith(b"\n"):
                    break
            raw = b"".join(chunks).decode("utf-8").strip()
            if not raw:
                return
            payload = json.loads(raw)

            req = _Request(payload)
            _requests.put(req)
            if not req.done.wait(timeout=880.0):
                reply = {"ok": False, "error": "timed out waiting for Blender main thread"}
            else:
                reply = req.reply
            conn.sendall((json.dumps(reply) + "\n").encode("utf-8"))
        except Exception:
            try:
                conn.sendall((json.dumps({"ok": False, "error": traceback.format_exc()}) + "\n").encode("utf-8"))
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


# ------------------------------------------------------------------------- ui

class COMICBLOCK_OT_start_bridge(bpy.types.Operator):
    bl_idname = "comicblock.start_bridge"
    bl_label = "Start Server"
    bl_description = "Open the loopback socket so external tooling can drive this session"

    def execute(self, context):
        global _server
        if _server is not None:
            self.report({"INFO"}, "Already running")
            return {"CANCELLED"}
        _server = BridgeServer()
        try:
            _server.start()
        except OSError as exc:
            _server = None
            self.report({"ERROR"}, "Could not bind {}: {}".format(PORT, exc))
            return {"CANCELLED"}
        self.report({"INFO"}, "Bridge listening on {}".format(PORT))
        return {"FINISHED"}


class COMICBLOCK_OT_stop_bridge(bpy.types.Operator):
    bl_idname = "comicblock.stop_bridge"
    bl_label = "Stop Server"

    def execute(self, context):
        global _server
        if _server is None:
            return {"CANCELLED"}
        _server.stop()
        _server = None
        self.report({"INFO"}, "Bridge stopped")
        return {"FINISHED"}


class COMICBLOCK_PT_bridge(bpy.types.Panel):
    bl_label = "comicblock"
    bl_idname = "COMICBLOCK_PT_bridge"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "comicblock"

    def draw(self, context):
        col = self.layout.column()
        running = _server is not None
        col.label(text="Bridge: " + ("listening on %d" % PORT if running else "stopped"),
                  icon="LINKED" if running else "UNLINKED")
        col.operator("comicblock.stop_bridge" if running else "comicblock.start_bridge")


_classes = (COMICBLOCK_OT_start_bridge, COMICBLOCK_OT_stop_bridge, COMICBLOCK_PT_bridge)


def register():
    for cls in _classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister():
    global _server
    if _server is not None:
        _server.stop()
        _server = None
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
    # Run from the Text Editor: start immediately so there is nothing else to click.
    if _server is None:
        _server = BridgeServer()
        try:
            _server.start()
        except OSError as exc:
            _server = None
            print("[comicblock bridge] could not bind port {}: {}".format(PORT, exc))
