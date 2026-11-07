"""Load a project's panel specs (panels.py, a PANELS dict). Pure Python: used by Blender and the CLI.

Spec format (see examples/starter/panels.py for working examples):

    "1": dict(
        size=(1536, 1024),                         # output pixels; keep the panel's own shape
        cam="WIDE",                                # a camera from project.yaml set.cameras, or ((x,y,z), (x,y,z))
        dolly=False,                               # True: move in from a named camera toward the cast (target ~35 mm)
        cast={"ada": dict(at=(x, y), face=(x, y), look="ben" | (x, y, z), pose={...}, world_ik={...})},
        props=[{"type": "box", ...}],              # see comicblock/bl/props.py
        doors={"Door": 70}, fourth=["4W_Study"],   # set state: door pivots (degrees), fourth walls shown
        show=[...], hide=[...],                    # object names (prefix match) to force on or off
        bottom="knees", pad=(l, r, t, b), frame_cast=[...], frame_extra=[(x,y,z)], max_lens=50, lens=None,
        hide_cast=False,                           # insert of a held prop: pose the cast, then hide the bodies
        action="One or two sentences: who does what, with what expression.",
        refs=[{"file": "refs/x.png", "text": "The second image ..."}],   # optional extra references
        outputs=2,
    )
"""
import importlib.util
import os


def load(root):
    path = os.path.join(root, "panels.py")
    if not os.path.isfile(path):
        raise SystemExit("No panels.py in %s" % root)
    spec = importlib.util.spec_from_file_location("cb_project_panels", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    panels = getattr(mod, "PANELS", None)
    if not isinstance(panels, dict):
        raise SystemExit("panels.py must define a PANELS dict")
    return {str(k): v for k, v in panels.items()}


def select(panels, ids):
    """ids: list of panel ids, or ["all"]. Unknown ids are an error (a typo should not silently skip a panel)."""
    if not ids or ids == ["all"]:
        return list(panels)
    missing = [i for i in ids if i not in panels]
    if missing:
        raise SystemExit("Unknown panel id(s): %s. Known: %s" % (", ".join(missing), ", ".join(panels)))
    return list(ids)
