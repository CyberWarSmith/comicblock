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


def run(cfg, command, args=(), blend=None, quiet=True):
    """Run a command in Blender; returns the decoded CB_RESULT payload. Raises SystemExit on failure."""
    exe = find(cfg)
    os.makedirs(cfg["paths"]["build"], exist_ok=True)
    rt = os.path.join(cfg["paths"]["build"], ".runtime.json")
    with open(rt, "w", encoding="utf-8") as fh:
        json.dump({"config": cfg, "command": command, "args": list(args)}, fh, indent=1)
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


def set_blend(cfg):
    path = os.path.join(cfg["paths"]["build"], "set.blend")
    if not os.path.isfile(path):
        raise SystemExit("No built set yet: run `comicblock build %s` first." % cfg["root"])
    return path
