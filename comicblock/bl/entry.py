"""Blender entry point for headless runs. The CLI runs:

    blender -b [file.blend] --python comicblock/bl/entry.py -- <runtime.json>

runtime.json holds the resolved project config plus {"command": ..., "args": [...]}. The result goes to stdout as a
line starting CB_RESULT (or CB_ERROR), which the CLI reads back. Live runs (--live) go through the bridge add-on
instead and call the same dispatch.run_file.
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    from comicblock.bl import dispatch
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ok = dispatch.run_file(argv[0])
    sys.stdout.flush()
    if not ok:
        os._exit(2)
except Exception:
    traceback.print_exc()
    print("CB_ERROR see traceback above")
    sys.stdout.flush()
    os._exit(1)
