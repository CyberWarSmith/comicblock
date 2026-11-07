"""Run one comicblock command inside Blender: headless (entry.py) or in the open session (the bridge, --live)."""
import json
import os
import sys


def run(rt, live=False):
    import bpy
    cfg, cmd, args = rt["config"], rt["command"], list(rt.get("args", []))
    if cfg["root"] not in sys.path:
        sys.path.insert(0, cfg["root"])                # project modules (panels.py, props.py) import from here
    from comicblock import panels as PN
    from comicblock.bl import stage as S
    blend = rt.get("blend")
    if live and blend:
        _ensure_open(blend)
    if cmd == "build":
        if live:
            set_blend = os.path.join(cfg["paths"]["build"], "set.blend")
            same = bpy.data.filepath and os.path.normcase(os.path.abspath(bpy.data.filepath)) == os.path.normcase(set_blend)
            if bpy.data.is_dirty and not same:
                raise SystemExit("The open Blender file has unsaved changes, and a live build clears the scene. Save "
                                 "it (or start File > New) and run again.")
        return S.build(cfg)
    if cmd == "plot":
        return S.plot(cfg, args or None)
    if cmd == "stage":
        panels = PN.load(cfg["root"])
        save = "--save" in args
        out = []
        for pid in PN.select(panels, [a for a in args if a != "--save"]):
            out.append(S.stage(cfg, pid, panels[pid]))
            if save:                                   # a copy to open and adjust by hand, then `comicblock render`
                d = os.path.join(cfg["paths"]["build"], "staged")
                os.makedirs(d, exist_ok=True)
                bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, "%s.blend" % pid), copy=True)
                out[-1]["saved"] = os.path.join(d, "%s.blend" % pid)
        return out
    if cmd == "render":
        return S.render_as_is(cfg, args[0])
    if cmd == "fit":
        from comicblock.bl import fit
        return fit.run(cfg, *args)
    raise SystemExit("unknown command %s" % cmd)


def _ensure_open(blend):
    """Live mode: switch the open session to `blend` unless it is already open (refuses over unsaved work)."""
    import bpy
    cur = bpy.data.filepath
    if cur and os.path.normcase(os.path.abspath(cur)) == os.path.normcase(os.path.abspath(blend)):
        return
    if bpy.data.is_dirty:
        raise SystemExit("Blender has unsaved changes in %s. Save or discard them, or open %s yourself, then run "
                         "again." % (cur or "an untitled file", blend))
    bpy.ops.wm.open_mainfile(filepath=blend)


def run_file(path, live=False):
    """Read a runtime.json, run it, and print the CB_RESULT / CB_ERROR line the CLI reads back."""
    with open(path, encoding="utf-8") as fh:
        rt = json.load(fh)
    try:
        result = run(rt, live=live)
    except SystemExit as e:
        print("CB_ERROR %s" % e)
        return False
    print("CB_RESULT " + json.dumps(result))
    return True
