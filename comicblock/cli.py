"""comicblock command line. Every command takes the project folder first.

    python -m comicblock doctor   <project>                  # check Blender, MPFB, Python packages, credentials
    python -m comicblock build    <project>                  # set + cast -> build/set.blend, build/plan.json
    python -m comicblock plan     <project>                  # floor plan with cameras -> build/plan.png
    python -m comicblock plot     <project> [CAM ...]        # empty-set renders per plot camera -> build/plot/
    python -m comicblock stage    <project> <id ...|all> [--save]   # blockouts -> blockout/<id>.png + .json
    python -m comicblock render   <project> <id> <file.blend | --live>   # hand-adjusted scene: render as it stands

    build, plot, stage and render take --live: run in the Blender window you have open (start the bridge add-on in
    blender_addon/comicblock_bridge.py first) so you can watch, instead of a hidden headless Blender.
    python -m comicblock prompt   <project> <id ...>         # print the prompt and references (no spend)
    python -m comicblock generate <project> <id ...> [--provider P] [--outputs N] [--dry]
    python -m comicblock import   <project> <id> <image ...> # bring in results made by hand (manual provider)
    python -m comicblock review   <project> <id ...|all> [--name NAME]   # contact sheet -> review/<name>.png
    python -m comicblock fit      <project> <character> <body.obj> [--up y|z]   # optional MPFB body fit
"""
import argparse
import os
import sys

from . import blender, config


def _cfg(ns):
    return config.load(ns.project)


def cmd_doctor(ns):
    import importlib
    ok = True
    for mod in ("yaml", "PIL", "numpy"):
        try:
            importlib.import_module(mod)
            print("ok    python package", mod)
        except ImportError:
            ok = False
            print("MISS  python package %s  (pip install -r requirements.txt)" % mod)
    cfg = _cfg(ns)
    try:
        exe = blender.find(cfg)
        print("ok    blender", exe)
    except SystemExit as e:
        print("MISS ", e)
        return 1
    import subprocess
    probe = ("import importlib,sys\nfor b in ('bl_ext.blender_org.mpfb','bl_ext.user_default.mpfb'):\n"
             "    try:\n        m=importlib.import_module(b); print('CB_MPFB', b); break\n"
             "    except Exception: pass\nelse: print('CB_MPFB none')\nprint('CB_VER', '.'.join(map(str, __import__('bpy').app.version)))")
    out = subprocess.run([exe, "-b", "--python-expr", probe], capture_output=True, text=True, errors="replace").stdout
    ver = [l.split()[1] for l in out.splitlines() if l.startswith("CB_VER")]
    mp = [l.split()[1] for l in out.splitlines() if l.startswith("CB_MPFB")]
    print("ok    blender version", ver[0] if ver else "?")
    if mp and mp[0] != "none":
        print("ok    MPFB extension", mp[0])
    else:
        ok = False
        print("MISS  MPFB extension: in Blender, Edit > Preferences > Get Extensions, search MPFB, Install")
    g = cfg["generation"]
    print("ok    provider", g["provider"], "model", g["model"])
    if g["provider"] == "scenario":
        from .providers.scenario import ScenarioProvider
        try:
            ScenarioProvider(cfg).credentials()
            print("ok    Scenario credentials found")
        except SystemExit as e:
            ok = False
            print("MISS ", e)
    for key, ch in cfg["characters"].items():
        miss = [s for s in ch["sheets"] if not str(s).startswith("asset_") and not os.path.isfile(config.resolve(cfg, s))]
        print(("ok   " if not miss else "MISS ") + " sheets for %s%s" % (key, (": missing " + ", ".join(miss)) if miss else ""))
        ok = ok and not miss
    return 0 if ok else 1


def cmd_build(ns):
    cfg = _cfg(ns)
    rep = blender.run(cfg, "build", live=ns.live)
    from . import plan
    print("built", os.path.join(cfg["paths"]["build"], "set.blend"))
    for k, v in rep.items():
        print("  %-12s visible height %.3f m" % (k, v["height"]))
    print("plan", plan.draw(cfg))


def cmd_plan(ns):
    from . import plan
    print(plan.draw(_cfg(ns)))


def cmd_plot(ns):
    cfg = _cfg(ns)
    done = blender.run(cfg, "plot", ns.cams, blend=blender.set_blend(cfg), live=ns.live)
    print("plot renders in", os.path.join(cfg["paths"]["build"], "plot"), ", ".join(done))


def cmd_stage(ns):
    cfg = _cfg(ns)
    extra = ["--save"] if ns.save else []
    if ns.live:                                          # one request per panel: watch each one land
        from . import panels as PN
        metas = []
        for pid in PN.select(PN.load(cfg["root"]), ns.ids):
            metas += blender.run(cfg, "stage", [pid] + extra, blend=blender.set_blend(cfg), live=True)
    else:
        metas = blender.run(cfg, "stage", ns.ids + extra, blend=blender.set_blend(cfg))
    for m in metas:
        print("%-8s lens %5.1f mm  features: %s" % (m["panel"], m["lens"], ", ".join(m["features"]) or "-"))
        print("         %s" % m["file"])
        if m.get("saved"):
            print("         staged scene to adjust by hand: %s" % m["saved"])
    print("Check every blockout at full size before generating.")


def cmd_render(ns):
    cfg = _cfg(ns)
    if ns.blend and not os.path.isfile(ns.blend):
        raise SystemExit("No such .blend: %s" % ns.blend)
    if not ns.blend and not ns.live:
        raise SystemExit("Give the adjusted .blend, or --live to render the scene open in Blender right now.")
    m = blender.run(cfg, "render", [ns.id], blend=os.path.abspath(ns.blend) if ns.blend else None, live=ns.live)
    print("%-8s rendered as it stands, lens %.1f mm  features: %s\n         %s" % (
        m["panel"], m["lens"], ", ".join(m["features"]) or "-", m["file"]))
    print("Make sure panel %s's action text in panels.py matches the new pose." % ns.id)


def cmd_prompt(ns):
    from . import generate
    cfg = _cfg(ns)
    generate.run(cfg, ns.ids, provider="dry")


def cmd_generate(ns):
    from . import generate
    cfg = _cfg(ns)
    return generate.run(cfg, ns.ids, provider="dry" if ns.dry else ns.provider, outputs=ns.outputs)


def cmd_import(ns):
    from . import generate
    generate.import_results(_cfg(ns), ns.id, ns.images)


def cmd_review(ns):
    from . import review
    print(review.sheet(_cfg(ns), ns.ids, ns.name))


def cmd_fit(ns):
    from . import bodyprofile
    cfg = _cfg(ns)
    if ns.character not in cfg["characters"]:
        raise SystemExit("No character %r in project.yaml" % ns.character)
    h = float(cfg["characters"][ns.character]["height"])
    tgt = bodyprofile.profile_obj(ns.mesh, h, up=ns.up)
    os.makedirs(os.path.join(cfg["root"], "cast"), exist_ok=True)
    tpath = os.path.join(cfg["root"], "cast", "%s.targets.json" % ns.character)
    bodyprofile.save_targets(tgt, tpath)
    print("target profile:", len(tgt), "slices ->", tpath)
    res = blender.run(cfg, "fit", [ns.character, tpath])
    print("fit error %.3f -> %.3f; wrote %s" % (res["start"], res["error"], res["file"]))
    print("Run `comicblock build` again to use it.")


def main(argv=None):
    p = argparse.ArgumentParser(prog="comicblock", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, *extra):
        sp = sub.add_parser(name)
        sp.add_argument("project")
        for a in extra:
            a(sp)
        sp.set_defaults(fn=fn)
        return sp
    ids = lambda sp: sp.add_argument("ids", nargs="*", default=["all"])
    add("doctor", cmd_doctor)
    live = lambda sp: sp.add_argument("--live", action="store_true",
                                      help="run in the Blender you have open (bridge add-on) instead of headless")
    add("build", cmd_build, live)
    add("plan", cmd_plan)
    add("plot", cmd_plot, lambda sp: sp.add_argument("cams", nargs="*"), live)
    add("stage", cmd_stage, ids, lambda sp: sp.add_argument("--save", action="store_true"), live)
    add("render", cmd_render, lambda sp: sp.add_argument("id"), lambda sp: sp.add_argument("blend", nargs="?"), live)
    add("prompt", cmd_prompt, lambda sp: sp.add_argument("ids", nargs="+"))
    add("generate", cmd_generate, lambda sp: sp.add_argument("ids", nargs="+"),
        lambda sp: sp.add_argument("--provider"), lambda sp: sp.add_argument("--outputs", type=int),
        lambda sp: sp.add_argument("--dry", action="store_true"))
    add("import", cmd_import, lambda sp: sp.add_argument("id"), lambda sp: sp.add_argument("images", nargs="+"))
    add("review", cmd_review, ids, lambda sp: sp.add_argument("--name"))
    add("fit", cmd_fit, lambda sp: sp.add_argument("character"), lambda sp: sp.add_argument("mesh"),
        lambda sp: sp.add_argument("--up", default="y", choices=("y", "z")))
    ns = p.parse_args(argv)
    return ns.fn(ns) or 0


if __name__ == "__main__":
    sys.exit(main())
