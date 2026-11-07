"""Build the set file, render plot cameras, and stage panels (runs inside Blender, launched by the CLI).

stage() rebuilds nothing: it opens the built set, sets the panel's set state, shows only its cast, poses and places
them, adds props, frames the camera, renders blockout/<id>.png and writes blockout/<id>.json (cast placement,
lens, the set features in frame). The set file is never saved by staging, so every run starts clean.
"""
import importlib.util
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

from . import cast as C
from . import features as F
from . import framing as FR
from . import kit
from . import posing as PO
from . import props as PR


def _set_module(cfg):
    path = cfg["set"]["script"]
    path = path if os.path.isabs(path) else os.path.join(cfg["root"], path)
    spec = importlib.util.spec_from_file_location("cb_project_set", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clear_scene():
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)


def write_plan(cfg, path):
    out = []
    room = bpy.data.collections.get(kit.ROOM)
    for o in (room.all_objects if room else []):
        if o.type != "MESH":
            continue
        ws = [o.matrix_world @ Vector(c) for c in o.bound_box]
        out.append(dict(name=o.name, x0=min(v.x for v in ws), x1=max(v.x for v in ws), y0=min(v.y for v in ws),
                        y1=max(v.y for v in ws), z0=min(v.z for v in ws), z1=max(v.z for v in ws)))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(dict(objects=out, rooms=cfg["set"]["rooms"], cameras=cfg["set"]["cameras"],
                       features={k: v["points"] for k, v in cfg["set"]["features"].items()},
                       cast={k: v["height"] for k, v in cfg["characters"].items()}), fh, indent=1)


def build(cfg):
    """Fresh scene -> set (the project's set.py build(kit)) -> cast -> render setup -> build/set.blend."""
    _clear_scene()
    kit.set_palette(cfg["set"]["palette"])
    kit.coll(kit.ROOM)
    mod = _set_module(cfg)
    vl = bpy.context.view_layer
    vl.active_layer_collection = vl.layer_collection.children[kit.ROOM]
    mod.build(kit)
    vl.active_layer_collection = vl.layer_collection
    kit.show_fourth(())
    kit.set_doors({})
    report = C.build_cast(cfg)
    C.show_cast([])
    kit.coll(PR.PROPS)
    C.setup_render(cfg)
    FR.camera()
    os.makedirs(cfg["paths"]["build"], exist_ok=True)
    write_plan(cfg, os.path.join(cfg["paths"]["build"], "plan.json"))
    out = os.path.join(cfg["paths"]["build"], "set.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=False)
    print("CB built", out, report)
    return report


def _set_state(cfg, spec, mod):
    kit.set_doors(spec.get("doors", {}))
    kit.show_fourth(spec.get("fourth", ()))
    kit.show_hide(spec.get("show", ()), spec.get("hide", ()))
    if hasattr(mod, "state"):                          # optional project hook: state(kit, spec)
        mod.state(kit, spec)


def plot(cfg, names=None, size=(1536, 1024)):
    """Render each plot camera of the empty set to build/plot/<name>.png (for checking the set and camera plot)."""
    kit.set_palette(cfg["set"]["palette"])
    mod = _set_module(cfg)
    C.show_cast([])
    PR.clear()
    out_dir = os.path.join(cfg["paths"]["build"], "plot")
    os.makedirs(out_dir, exist_ok=True)
    done = []
    for name in names or list(cfg["set"]["cameras"]):
        c = cfg["set"]["cameras"][name]
        _set_state(cfg, {"doors": c.get("doors", {}), "fourth": c.get("fourth", ())}, mod)
        FR.aim(c["pos"], c["look"], c.get("lens", 24), *size)
        bpy.context.scene.render.filepath = os.path.join(out_dir, name + ".png")
        bpy.ops.render.render(write_still=True)
        done.append(name)
        print("CB plot", name)
    return done


def render_as_is(cfg, pid, fourth=()):
    """Render a .blend the artist has adjusted by hand, exactly as it stands (no posing, no framing), and record
    the features in frame. Re-staging would reset their work. The prompt's action text still comes from panels.py,
    so update it to match the new pose."""
    sc = bpy.context.scene
    if sc.camera is None:
        raise SystemExit("This .blend has no active camera")
    out_dir = cfg["paths"]["blockout"]
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%s.png" % pid)
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    shown = fourth or [o.name for o in bpy.data.objects if o.name.startswith("4W_") and "_" not in o.name[3:] and not o.hide_render]
    cam = sc.camera
    meta = dict(panel=pid, file=out, size=[sc.render.resolution_x, sc.render.resolution_y],
                lens=round(cam.data.lens, 1), shift=[round(cam.data.shift_x, 3), round(cam.data.shift_y, 3)],
                camera=[round(v, 3) for v in cam.location], cast={}, hide_cast=False, as_is=True,
                features=F.visible(cfg["set"]["features"], shown))
    with open(os.path.join(out_dir, "%s.json" % pid), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print("CB rendered as is", pid, meta["features"])
    return meta


def _camera_for(cfg, spec):
    cam = spec["cam"]
    if isinstance(cam, str):
        c = cfg["set"]["cameras"].get(cam)
        if c is None:
            raise SystemExit("Camera %r is not in project.yaml set.cameras" % cam)
        return c["pos"], c["look"], c
    return cam[0], cam[1], {}


def stage(cfg, pid, spec, render=True):
    kit.set_palette(cfg["set"]["palette"])
    mod = _set_module(cfg)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    keys = list(spec.get("cast", {}))
    unknown = [k for k in keys if k not in C.cast_keys()]
    if unknown:
        raise SystemExit("Panel %s: no mannequin for %s (rebuild after adding characters)" % (pid, ", ".join(unknown)))
    pos, look, camdef = _camera_for(cfg, spec)
    fourth = spec.get("fourth", camdef.get("fourth", ()))
    _set_state(cfg, dict(spec, fourth=fourth, doors=spec.get("doors", camdef.get("doors", {}))), mod)
    C.show_cast(keys)
    PR.clear()
    rigs = {k: C.rig(k) for k in keys}
    for k, arm in rigs.items():
        c = spec["cast"][k]
        PO.pose(arm, c.get("pose", {"root": 0.0}))
        PO.place(arm, c["at"], c["face"], c.get("lift", 0.0))
        PO.world_ik(arm, c.get("world_ik"))
    for k, arm in rigs.items():
        look_at = spec["cast"][k].get("look")
        if look_at is not None:
            PO.aim_eyes(arm, PO.head_world(rigs[look_at]) if isinstance(look_at, str) else Vector(look_at))
    PR.place_all(cfg, spec, rigs)
    w, h = spec.get("size", cfg["render"]["default_size"])
    extra = list(spec.get("frame_extra", ())) + (PR.bounds_points() if spec.get("frame_props", True) else [])
    frame_keys = spec.get("frame_cast", keys)
    args = (w, h, frame_keys, spec.get("bottom", "knees"), spec.get("pad", (0.06, 0.06, 0.08, 0.02)), extra)
    if spec.get("lens"):                               # fixed lens (wide establishing shots): no fitting
        cam = FR.aim(pos, look, spec["lens"], w, h, tuple(spec.get("shift", (0.0, 0.0))))
    elif spec.get("dolly"):
        cam = FR.dolly_frame(pos, look, *args, max_lens=spec.get("max_lens", 50.0),
                             target_lens=spec.get("target_lens", 35.0), min_dist=spec.get("min_dist", 1.0),
                             bounds=cfg["set"].get("bounds"))
    elif frame_keys or extra:
        cam = FR.frame_at(pos, look, *args, max_lens=spec.get("max_lens", 50.0))
    else:
        cam = FR.aim(pos, look, camdef.get("lens", 24), w, h)
    if spec.get("roll"):                               # dutch angle (degrees about the view axis)
        cam.matrix_world = cam.matrix_world @ Matrix.Rotation(math.radians(spec["roll"]), 4, "Z")
        bpy.context.view_layer.update()
    if spec.get("hide_cast"):                          # insert of a held prop: posed, framed, then not rendered
        C.show_cast([], render_only=True)
    feats = F.visible(cfg["set"]["features"], fourth)
    out_dir = cfg["paths"]["blockout"]
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "%s.png" % pid)
    if render:
        sc = bpy.context.scene
        sc.render.filepath = out
        bpy.ops.render.render(write_still=True)
    meta = dict(panel=pid, file=out, size=[w, h], lens=round(cam.data.lens, 1),
                shift=[round(cam.data.shift_x, 3), round(cam.data.shift_y, 3)],
                camera=[round(v, 3) for v in cam.location],
                cast={k: dict(at=[round(v, 2) for v in a.location[:2]], yaw=round(math.degrees(a.rotation_euler.z), 1))
                      for k, a in rigs.items()},
                hide_cast=bool(spec.get("hide_cast")), features=feats)
    with open(os.path.join(out_dir, "%s.json" % pid), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print("CB staged", pid, "lens %.1f" % meta["lens"], "features", feats)
    return meta
