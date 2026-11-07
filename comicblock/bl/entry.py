"""Blender entry point. The CLI runs:

    blender -b [build/set.blend] --python comicblock/bl/entry.py -- <runtime.json>

runtime.json holds the resolved project config plus {"command": ..., "args": [...]}. Results go to stdout as a line
starting CB_RESULT, which the CLI reads back.
"""
import json
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    with open(argv[0], encoding="utf-8") as fh:
        rt = json.load(fh)
    cfg, cmd, args = rt["config"], rt["command"], rt.get("args", [])
    sys.path.insert(0, cfg["root"])                    # project modules (panels.py, props.py) import from here
    from comicblock.bl import stage as S
    from comicblock import panels as PN
    if cmd == "build":
        result = S.build(cfg)
    elif cmd == "plot":
        result = S.plot(cfg, args or None)
    elif cmd == "stage":
        import bpy
        panels = PN.load(cfg["root"])
        save = "--save" in args
        result = []
        for pid in PN.select(panels, [a for a in args if a != "--save"]):
            result.append(S.stage(cfg, pid, panels[pid]))
            if save:                                   # a copy to open and adjust by hand, then `comicblock render`
                d = os.path.join(cfg["paths"]["build"], "staged")
                os.makedirs(d, exist_ok=True)
                bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, "%s.blend" % pid), copy=True)
                result[-1]["saved"] = os.path.join(d, "%s.blend" % pid)
    elif cmd == "render":
        result = S.render_as_is(cfg, args[0])
    elif cmd == "fit":
        from comicblock.bl import fit
        result = fit.run(cfg, *args)
    else:
        raise SystemExit("unknown command %s" % cmd)
    print("CB_RESULT " + json.dumps(result))


try:
    main()
except SystemExit as e:
    print("CB_ERROR %s" % e)
    sys.stdout.flush()
    os._exit(2)
except Exception:
    traceback.print_exc()
    print("CB_ERROR see traceback above")
    sys.stdout.flush()
    os._exit(1)
