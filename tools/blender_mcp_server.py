# /// script
# requires-python = ">=3.10"
# dependencies = ["mcp>=2,<3"]
# ///
"""
comicblock - MCP server fronting a running Blender session, so Claude Code can look at and work in the
Blender you have open (inspect a scene you adjusted by hand, try a pose, render the current camera).

Talks to the loopback socket opened by blender_addon/comicblock_bridge.py. Start that inside Blender first
(Text Editor > Alt+P, or install it as an add-on and press Start Server in the sidebar), then these tools work.
Registered for Claude Code in the repo's .mcp.json. Needs uv (https://docs.astral.sh/uv/).

Run standalone for a connection check:
    uv run --script tools/blender_mcp_server.py --selftest
"""

import json
import os
import socket
import sys

from mcp.server.mcpserver import MCPServer

HOST = "127.0.0.1"
PORT = int(os.environ.get("COMICBLOCK_BRIDGE_PORT", "9876"))
TIMEOUT = 900.0

# mcp 2.x renamed FastMCP to MCPServer; the decorator and run() are unchanged.
mcp = MCPServer("blender")


class BlenderDown(RuntimeError):
    pass


def _call(payload: dict) -> dict:
    """One request per connection. Stateless, so a Blender restart needs no resync."""
    try:
        with socket.create_connection((HOST, PORT), timeout=10.0) as sock:
            sock.settimeout(TIMEOUT)
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            chunks = []
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
                if data.endswith(b"\n"):
                    break
    except (ConnectionRefusedError, OSError) as exc:
        raise BlenderDown(
            "Cannot reach Blender on {}:{} ({}). Open Blender, load "
            "blender_addon/comicblock_bridge.py in the Text Editor and press Alt+P.".format(HOST, PORT, exc)
        ) from exc

    raw = b"".join(chunks).decode("utf-8").strip()
    if not raw:
        raise BlenderDown("Blender closed the connection without replying.")
    return json.loads(raw)


def _format(reply: dict) -> str:
    parts = []
    if reply.get("stdout"):
        parts.append(reply["stdout"].rstrip())
    if "result" in reply:
        parts.append("result = " + reply["result"])
    if not reply.get("ok", False):
        parts.append("ERROR:\n" + reply.get("error", "unknown"))
    return "\n".join(parts) if parts else "(no output)"


@mcp.tool()
def blender_exec(code: str) -> str:
    """Execute Python inside the running Blender session.

    `bpy` is already in scope. Anything printed comes back, and assigning to a
    variable named `result` returns its repr as well. Runs on Blender's main thread,
    so it is safe to touch any part of the API.
    """
    try:
        return _format(_call({"cmd": "exec", "code": code}))
    except BlenderDown as exc:
        return str(exc)


@mcp.tool()
def blender_scene_info() -> str:
    """Objects, collections, render engine and current frame in the open session."""
    try:
        reply = _call({"cmd": "scene_info"})
    except BlenderDown as exc:
        return str(exc)
    if not reply.get("ok"):
        return "ERROR: " + reply.get("error", "unknown")
    return json.dumps(reply, indent=2)


@mcp.tool()
def blender_ping() -> str:
    """Check whether the bridge is up, and report the Blender version."""
    try:
        reply = _call({"cmd": "ping"})
    except BlenderDown as exc:
        return str(exc)
    return "connected to Blender " + reply.get("blender", "?")


@mcp.tool()
def blender_render(output_path: str, samples: int = 16, resolution: int = 0) -> str:
    """Render the current camera to a PNG and return the path.

    Renders whatever camera the scene currently has active. resolution 0 keeps the scene's own size (a staged
    panel's size); otherwise it is the longest edge, keeping the scene's aspect. Use blender_exec first to place or
    switch cameras. For a panel blockout, prefer `python -m comicblock render <project> <id> --live`, which also
    records the set features in frame.
    """
    code = f"""
import os
scene = bpy.context.scene
if scene.camera is None:
    print("no active camera in scene")
else:
    if {int(resolution)} > 0:
        k = {int(resolution)} / max(scene.render.resolution_x, scene.render.resolution_y)
        scene.render.resolution_x = round(scene.render.resolution_x * k)
        scene.render.resolution_y = round(scene.render.resolution_y * k)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    try:
        scene.eevee.taa_render_samples = {int(samples)}
    except Exception:
        pass
    scene.render.filepath = os.path.abspath(r"{output_path}")
    bpy.ops.render.render(write_still=True)
    result = scene.render.filepath
"""
    try:
        return _format(_call({"cmd": "exec", "code": code}))
    except BlenderDown as exc:
        return str(exc)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        try:
            print("connected to Blender", _call({"cmd": "ping"}).get("blender", "?"))
            print(json.dumps(_call({"cmd": "scene_info"}), indent=2)[:800])
        except BlenderDown as exc:
            print("SELFTEST FAILED:", exc)
            sys.exit(1)
        sys.exit(0)
    mcp.run()
