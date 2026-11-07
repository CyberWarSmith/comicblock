"""Find Blender and run a comicblock command inside it (headless)."""
import glob
import json
import os
import platform
import shutil
import subprocess
import sys

ENTRY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bl", "entry.py")


def find(cfg):
    want = cfg.get("blender") or "auto"
    if want != "auto":
        path = os.path.expanduser(want)
        if not os.path.isfile(path):
            raise SystemExit("project.yaml blender: %s does not exist" % path)
        return path
    env = os.environ.get("COMICBLOCK_BLENDER")
    if env and os.path.isfile(env):
        return env
    found = shutil.which("blender")
    if found:
        return found
    cands = []
    if platform.system() == "Windows":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), r"C:\Program Files"):
            cands += glob.glob(os.path.join(base, "Blender Foundation", "Blender *", "blender.exe"))
    elif platform.system() == "Darwin":
        cands += glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender")
    else:
        cands += glob.glob("/opt/blender*/blender") + glob.glob(os.path.expanduser("~/blender*/blender"))

    def ver(p):
        import re
        m = re.search(r"(\d+)\.(\d+)", p)
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    if cands:
        return max(cands, key=ver)
    raise SystemExit("Blender not found. Install Blender 4.2+ (5.1 tested), or set `blender:` in project.yaml "
                     "or the COMICBLOCK_BLENDER environment variable to blender's path.")


def _write_runtime(cfg, command, args, blend):
    os.makedirs(cfg["paths"]["build"], exist_ok=True)
    rt = os.path.join(cfg["paths"]["build"], ".runtime.json")
    with open(rt, "w", encoding="utf-8") as fh:
        json.dump({"config": cfg, "command": command, "args": list(args), "blend": blend}, fh, indent=1)
    return rt


def run(cfg, command, args=(), blend=None, quiet=True, live=False):
    """Run a command in Blender; returns the decoded CB_RESULT payload. Raises SystemExit on failure.
    live=True runs it in the Blender session you have open (needs the bridge add-on running) instead of a
    headless Blender; that session switches to `blend` first if a different, saved file is open."""
    if live:
        return run_live(cfg, command, args, blend)
    exe = find(cfg)
    rt = _write_runtime(cfg, command, args, blend)
    cmd = [exe, "-b"] + ([blend] if blend else []) + ["--python", ENTRY, "--", rt]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            encoding="utf-8", errors="replace")
    result, error, tail = None, None, []
    for line in proc.stdout:
        line = line.rstrip("\n")
        tail = (tail + [line])[-60:]
        if line.startswith("CB_RESULT "):
            result = json.loads(line[10:])
        elif line.startswith("CB_ERROR "):
            error = line[9:]
        elif line.startswith("CB ") or line.startswith("cast:") or not quiet:
            print(line, flush=True)
    proc.wait()
    if error or result is None:
        print("\n".join(tail), file=sys.stderr)
        raise SystemExit("Blender %s failed: %s" % (command, error or "no result (exit %s)" % proc.returncode))
    return result


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_CODE = r'''
import sys
for _m in [m for m in sys.modules if m == "comicblock" or m.startswith("comicblock.")]:
    del sys.modules[_m]                     # pick up edits to comicblock without restarting Blender
if {repo!r} not in sys.path:
    sys.path.insert(0, {repo!r})
from comicblock.bl import dispatch
dispatch.run_file({rt!r}, live=True)
'''


def bridge_call(payload, timeout=900.0):
    import socket
    port = int(os.environ.get("COMICBLOCK_BRIDGE_PORT", "9876"))
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=10.0) as sock:
            sock.settimeout(timeout)
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            chunks = []
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
                if data.endswith(b"\n"):
                    break
    except OSError as exc:
        raise SystemExit("No live Blender on port %d (%s). Open Blender, load blender_addon/comicblock_bridge.py "
                         "in the Text Editor and press Alt+P (or Start Server in the sidebar's comicblock tab), "
                         "or run without --live." % (port, exc))
    raw = b"".join(chunks).decode("utf-8").strip()
    if not raw or raw == "null":
        raise SystemExit("The live Blender closed the connection without replying.")
    return json.loads(raw)


def run_live(cfg, command, args, blend):
    rt = _write_runtime(cfg, command, args, blend)
    reply = bridge_call({"cmd": "exec", "code": LIVE_CODE.format(repo=REPO, rt=rt)})
    result, error = None, None
    for line in (reply.get("stdout") or "").splitlines():
        if line.startswith("CB_RESULT "):
            result = json.loads(line[10:])
        elif line.startswith("CB_ERROR "):
            error = line[9:]
        elif line.startswith("CB ") or line.startswith("cast:"):
            print(line, flush=True)
    if not reply.get("ok"):
        print(reply.get("stdout", ""), file=sys.stderr)
        raise SystemExit("Live Blender %s failed:\n%s" % (command, reply.get("error", "unknown")))
    if error or result is None:
        raise SystemExit("Live Blender %s failed: %s" % (command, error or "no result"))
    return result


def set_blend(cfg):
    path = os.path.join(cfg["paths"]["build"], "set.blend")
    if not os.path.isfile(path):
        raise SystemExit("No built set yet: run `comicblock build %s` first." % cfg["root"])
    return path
