"""Prop proxies placed per panel (runs inside Blender). Built fresh each time a panel is staged, in CAST_PROPS.

A spec's props list holds dicts with a "type". Built in:

    {"type": "box", "lo": (x, y, z), "hi": (x, y, z), "colour": "bag"}
    {"type": "cylinder", "at": (x, y, z), "r": 0.04, "h": 0.1, "colour": "cream"}
    {"type": "held", "who": "ada", "hand": "R", "size": (0.20, 0.03, 0.28), "colour": "book"}   # in the hand
    {"type": "shoulder_bag", "who": "ada", "side": "R"}

A project can add its own types in a props.py next to project.yaml (set.props: props.py):

    def mug(kit, ctx, at, colour="cream"):        # ctx: {"rigs": {key: armature}, "spec": the panel spec}
        return kit.cyl("PROP_Mug", at, 0.045, 0.10, kit.m(colour), collection=kit.coll("CAST_PROPS"))

then {"type": "mug", "at": (2.4, 3.4, 0.45)}. Names must start with PROP_ so they are cleared between panels.
Model the details that decide the read: a prop in an empty hand is otherwise invented by the model, and a flat hand
can't show palm versus back.
"""
import importlib.util
import os

import bpy
from mathutils import Matrix, Vector

from . import kit

PROPS = "CAST_PROPS"


def coll():
    return kit.coll(PROPS)


def clear():
    for o in [o for o in bpy.data.objects if o.name.startswith("PROP_")]:
        bpy.data.objects.remove(o)
    for me in [me for me in bpy.data.meshes if me.users == 0]:
        bpy.data.meshes.remove(me)


def _parent_to_bone(o, arm, bone):
    mw = o.matrix_world.copy()
    o.parent = arm
    o.parent_type = "BONE"
    o.parent_bone = bone
    o.matrix_world = mw


def box(ctx, lo, hi, colour="prop", name="PROP_Box"):
    return kit.box(name, lo, hi, kit.m(colour), coll())


def cylinder(ctx, at, r=0.04, h=0.1, colour="prop", name="PROP_Cyl"):
    return kit.cyl(name, at, r, h, kit.m(colour), collection=coll())


def held(ctx, who, hand="R", size=(0.16, 0.22, 0.03), colour="prop", name=None, along=0.0):
    """A box gripped in a hand (book, phone, card), centred in the palm and parented to the wrist.
    size = (across the palm, along the fingers, thickness). `along` slides it toward the fingertips (metres).
    Set the hand's grip to ~60-70 in the pose so the fingers close on it."""
    arm = ctx["rigs"][who]
    s = hand.upper()
    W = lambda b: arm.matrix_world @ arm.pose.bones[b].head
    wrist, knuckle = W("wrist.%s" % s), W("finger3-1.%s" % s)
    side_a, side_b = W("finger2-1.%s" % s), W("finger5-1.%s" % s)
    y = (knuckle - wrist).normalized()
    x = (side_b - side_a)
    x = (x - y * x.dot(y)).normalized()
    z = x.cross(y)
    centre = wrist.lerp(knuckle, 0.6) + y * along
    sx, sy, sz = size
    o = kit.box(name or "PROP_Held_%s_%s" % (who, s), (-sx / 2, -sy / 2, -sz / 2), (sx / 2, sy / 2, sz / 2),
                kit.m(colour), coll())
    rot = Matrix((x, y, z)).transposed().to_4x4()
    o.matrix_world = Matrix.Translation(centre) @ rot
    bpy.context.view_layer.update()
    _parent_to_bone(o, arm, "wrist.%s" % s)
    return o


def shoulder_bag(ctx, who, side="R", colour="bag"):
    """A bag on a strap over one shoulder, hanging at the hip (rest frame: +X is the character's left)."""
    arm = ctx["rigs"][who]
    s = -1 if side.upper() == "R" else 1
    mw = arm.matrix_world
    bag = kit.box("PROP_Bag_" + who, (s * 0.22 - 0.05, -0.10, 0.80), (s * 0.22 + 0.07, 0.20, 1.05), kit.m(colour), coll())
    bag.matrix_world = mw @ bag.matrix_world
    sh = mw @ arm.pose.bones["upperarm01.%s" % ("R" if s < 0 else "L")].head
    hip = mw @ Vector((s * 0.22, 0.05, 1.05))
    kit.rod("PROP_Strap_" + who, sh + Vector((0, 0, 0.03)), hip, 0.012, kit.m(colour), coll())
    return bag


BUILTIN = {"box": box, "cylinder": cylinder, "held": held, "shoulder_bag": shoulder_bag}


def _project_module(cfg):
    path = cfg["set"].get("props")
    if not path:
        return None
    path = path if os.path.isabs(path) else os.path.join(cfg["root"], path)
    spec = importlib.util.spec_from_file_location("cb_project_props", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def place_all(cfg, spec, rigs):
    ctx = {"rigs": rigs, "spec": spec, "cfg": cfg}
    mod = _project_module(cfg)
    for i, p in enumerate(spec.get("props", [])):
        p = dict(p)
        kind = p.pop("type")
        if mod and hasattr(mod, kind):
            getattr(mod, kind)(kit, ctx, **p)
        elif kind in BUILTIN:
            BUILTIN[kind](ctx, **p)
        else:
            raise SystemExit("Unknown prop type %r (built in: %s; add it to the project's props.py)" % (kind, ", ".join(BUILTIN)))
    bpy.context.view_layer.update()


def bounds_points():
    """World corners of every prop, so framing can keep held props in shot."""
    out = []
    for o in bpy.data.objects:
        if o.name.startswith("PROP_") and o.type == "MESH" and not o.hide_render:
            out += [tuple(o.matrix_world @ Vector(c)) for c in o.bound_box]
    return out
