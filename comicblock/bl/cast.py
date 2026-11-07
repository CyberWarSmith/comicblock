"""Cast mannequins (runs inside Blender): MPFB humans at true height, the "Default no toes" rig with MPFB's IK
helpers, flat grey with dark eyes, and the outline-only Freestyle ink.

MPFB (MakeHuman for Blender, GPL) is a dependency the user installs as a Blender extension; nothing from it is
bundled here. Per character in project.yaml:

    characters:
      ada:
        height: 1.68                      # metres, measured on the visible body
        mpfb:
          macros: {gender: 0.0, age: 0.5, muscle: 0.5, weight: 0.5, proportions: 0.5, cupsize: 0.5}
          targets: {"measure-waist-circ": -0.25}     # signed: + loads <stem>-incr, - loads <stem>-decr
"""
import importlib
import json
import os

import bpy
import numpy as np

CAST = "CAST"
VISIBLE = "CB_visible"         # vertex group: body + eyes (MPFB's helper geometry is masked away)


def mpfb():
    """MPFB's package, wherever the extension repository put it."""
    for base in ("bl_ext.blender_org.mpfb", "bl_ext.user_default.mpfb"):
        try:
            return importlib.import_module(base)
        except ImportError:
            continue
    import sys
    for name in list(sys.modules):
        if name.startswith("bl_ext.") and name.endswith(".mpfb"):
            return sys.modules[name]
    raise SystemExit("MPFB is not installed or not enabled in this Blender. Install it from Edit > Preferences > "
                     "Get Extensions (search 'MPFB'), then run again.")


def _svc(sub):
    return importlib.import_module(mpfb().__name__ + "." + sub)


def body_name(key):
    return "CB_" + key


def rig_name(key):
    return "CB_" + key + ".rig"


def rig(key):
    return bpy.data.objects[rig_name(key)]


def body(key):
    return bpy.data.objects[body_name(key)]


# ------------------------------------------------------------------ shape

def set_target(obj, stem, v):
    ts = _svc("services.targetservice").TargetService
    kb = obj.data.shape_keys.key_blocks if obj.data.shape_keys else {}
    for suffix, val in (("incr", max(v, 0.0)), ("decr", max(-v, 0.0))):
        name = "%s-%s" % (stem, suffix)
        if name in kb:
            kb[name].value = val
        elif val > 0:
            ts.load_target(obj, ts.target_full_path(name), weight=val)
        kb = obj.data.shape_keys.key_blocks if obj.data.shape_keys else {}


def set_macro(obj, name, v):
    HP = _svc("entities.objectproperties").HumanObjectProperties
    HP.set_value(name, v, entity_reference=obj)
    _svc("services.targetservice").TargetService.reapply_macro_details(obj)


def _visible_co(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    c = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", c)
    ev.to_mesh_clear()
    c = c.reshape(-1, 3)
    M = np.array(obj.matrix_world)
    return c @ M[:3, :3].T + M[:3, 3]


def visible_height(obj):
    return float(np.ptp(_visible_co(obj)[:, 2]))


def fit_height(obj, height):
    """Bisect MPFB's height macro until the visible (masked) body is `height` metres tall."""
    lo, hi, mid = 0.0, 1.0, 0.5
    for _ in range(20):
        mid = (lo + hi) / 2
        set_macro(obj, "height", mid)
        h = visible_height(obj)
        if abs(h - height) < 0.0008:
            break
        lo, hi = (mid, hi) if h < height else (lo, mid)
    return mid, h


def _mask_and_materials(obj, grey, eyes):
    groups = {vg.name: vg.index for vg in obj.vertex_groups}
    keep = {groups[n] for n in ("body", "helper-l-eye", "helper-r-eye") if n in groups}
    eye_g = {groups[n] for n in ("helper-l-eye", "helper-r-eye") if n in groups}
    vis = obj.vertex_groups.get(VISIBLE) or obj.vertex_groups.new(name=VISIBLE)
    members, eye_v = [], set()
    for v in obj.data.vertices:
        gs = {g.group for g in v.groups if g.weight > 0}
        if gs & keep:
            members.append(v.index)
        if gs & eye_g:
            eye_v.add(v.index)
    vis.add(members, 1.0, "REPLACE")
    mod = obj.modifiers.get("CB visible") or obj.modifiers.new("CB visible", "MASK")
    mod.vertex_group = VISIBLE
    from . import kit
    obj.data.materials.clear()
    obj.data.materials.append(kit.flat("CB_MANNEQUIN_FLAT", grey))
    obj.data.materials.append(kit.flat("CB_MANNEQUIN_EYES", eyes))
    for p in obj.data.polygons:
        p.material_index = 1 if all(i in eye_v for i in p.vertices) else 0


def _ground(obj):
    """Put the lowest visible vertex on z = 0 (macro changes move the feet)."""
    z = float(_visible_co(obj)[:, 2].min())
    obj.location.z -= z
    bpy.context.view_layer.update()


HELPER_SETTINGS = {
    "arm_helpers_type": "LOWERUPPER", "arm_parenting_strategy": "SPINE", "arm_target_rotates_hand": True,
    "arm_target_rotates_lower_arm": True, "eye_ik": True, "eye_parenting_strategy": "HEAD",
    "finger_helpers_type": "GRIP_AND_MASTER", "hide_fk": True, "leg_helpers_type": "LOWERUPPER",
    "leg_parenting_strategy": "NONE", "leg_target_rotates_foot": True, "leg_target_rotates_lower_leg": True,
    "preserve_fk": True,
}


def _add_helpers(arm_obj):
    """MPFB's default IK helpers: hand/elbow and foot/knee targets, finger grips, an eye_ik gaze target."""
    vl = bpy.context.view_layer
    for o in bpy.context.selected_objects:
        o.select_set(False)
    vl.objects.active = arm_obj
    arm_obj.select_set(True)
    rh = "entities.rigging.righelpers."
    Arm = _svc(rh + "armhelpers.armhelpers").ArmHelpers
    Leg = _svc(rh + "leghelpers.leghelpers").LegHelpers
    Fin = _svc(rh + "fingerhelpers.fingerhelpers").FingerHelpers
    Eye = _svc(rh + "eyehelpers.eyehelpers").EyeHelpers
    s = dict(HELPER_SETTINGS)
    for side in ("left", "right"):
        Arm.get_instance(side, s).apply_ik(arm_obj)
        Leg.get_instance(side, s).apply_ik(arm_obj)
        Fin.get_instance(side, s).apply_ik(arm_obj)
    Eye.get_instance(s).apply_ik(arm_obj)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    _svc("services.rigservice").RigService.normalize_rotation_mode(arm_obj)


def fit_file(cfg, key):
    return os.path.join(cfg["root"], "cast", "%s.fit.json" % key)


def create_human(key, ch, cfg, rigged=True):
    """Build one character. A body fit written by `comicblock fit` (cast/<key>.fit.json) overrides project.yaml's
    mpfb macros and targets."""
    HS = _svc("services.humanservice").HumanService
    TS = _svc("services.targetservice").TargetService
    spec = dict(ch.get("mpfb") or {})
    fitted = fit_file(cfg, key)
    if os.path.isfile(fitted):
        with open(fitted, encoding="utf-8") as fh:
            f = json.load(fh)
        spec = {"macros": {**spec.get("macros", {}), **f.get("macros", {})}, "targets": f.get("targets", {})}
    macro = TS.get_default_macro_info_dict()
    for k, v in (spec.get("macros") or {}).items():
        if k in macro.get("race", {}):
            macro["race"][k] = v
        else:
            macro[k] = v
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj = HS.create_human(mask_helpers=False, detailed_helpers=True, extra_vertex_groups=True,
                          feet_on_ground=True, macro_detail_dict=macro)
    obj.name = obj.data.name = body_name(key)
    for stem, v in (spec.get("targets") or {}).items():
        set_target(obj, stem, float(v))
    _mask_and_materials(obj, cfg["cast"]["grey"], cfg["cast"]["eyes"])
    hmacro, h = fit_height(obj, float(ch["height"]))
    _ground(obj)
    obj["cb_height"] = round(h, 4)
    if not rigged:
        return obj, None
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    arm = HS.add_builtin_rig(obj, cfg["cast"].get("rig", "default_no_toes"))
    arm.name = arm.data.name = rig_name(key)
    _add_helpers(arm)
    # MPFB adds an Armature modifier last; keep the mask after it so the masked body deforms.
    mods = obj.modifiers
    if mods.find("CB visible") < mods.find("Armature"):
        with bpy.context.temp_override(object=obj):
            bpy.ops.object.modifier_move_to_index(modifier="CB visible", index=len(mods) - 1)
    return obj, arm


def build_cast(cfg):
    c = bpy.data.collections.get(CAST) or bpy.data.collections.new(CAST)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    report = {}
    for key, ch in cfg["characters"].items():
        obj, arm = create_human(key, ch, cfg)
        for o in [obj, arm] + list(arm.children):
            for uc in list(o.users_collection):
                uc.objects.unlink(o)
            c.objects.link(o)
        report[key] = dict(height=obj["cb_height"], rig=arm.name)
        print("cast:", key, report[key])
    return report


def show_cast(keys, render_only=False):
    """Show these characters, hide the rest. render_only: hide from the render but keep them for framing."""
    for k in cast_keys():
        vis = k in keys
        for o in (rig(k), body(k)):
            o.hide_render = not vis
            if not render_only:
                o.hide_viewport = not vis


def cast_keys():
    return {o.name[3:-4] for o in bpy.data.objects if o.type == "ARMATURE" and o.name.startswith("CB_") and o.name.endswith(".rig")}


# ------------------------------------------------------------------ render and ink

def setup_render(cfg):
    """EEVEE, standard colour, grey world, and two Freestyle line sets: the set's ink (everything but the cast)
    and an outline-only line set for the cast. Fully inked, shaded nude mannequins get refused by content
    filters; flat grey with an outline passes."""
    sc = bpy.context.scene
    r = cfg["render"]
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items} else "BLENDER_EEVEE_NEXT"
    sc.view_settings.view_transform = "Standard"
    try:
        sc.eevee.taa_render_samples = int(r["samples"])
    except AttributeError:
        pass
    sc.render.resolution_x, sc.render.resolution_y = r["default_size"]
    sc.render.resolution_percentage = 100
    world = sc.world or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background") or world.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs[0].default_value = tuple(r["background"]) + (1,)
    bg.inputs[1].default_value = r["background_strength"]
    out = world.node_tree.nodes.get("World Output") or world.node_tree.nodes.new("ShaderNodeOutputWorld")
    if not bg.outputs[0].links:
        world.node_tree.links.new(bg.outputs[0], out.inputs[0])
    sc.render.use_freestyle = True
    sc.render.line_thickness_mode = "ABSOLUTE"
    sc.render.line_thickness = 1.0
    vl = bpy.context.view_layer
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.mode = "EDITOR"
    fs.use_culling = True                 # lines only for what the camera sees (big sets hang otherwise)
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    cast = bpy.data.collections.get(CAST) or bpy.data.collections.new(CAST)
    ink = fs.linesets.new("SetInk")
    ink.select_by_visibility = ink.select_by_edge_types = ink.select_by_collection = True
    ink.visibility = "VISIBLE"
    for k in ("select_silhouette", "select_border", "select_crease", "select_edge_mark", "select_external_contour"):
        setattr(ink, k, True)
    ink.collection = cast
    ink.collection_negation = "EXCLUSIVE"
    ink.linestyle.color = (0.09, 0.07, 0.08)
    ink.linestyle.thickness = float(cfg["cast"]["ink"])
    out_ls = fs.linesets.new("CastOutline")
    out_ls.select_by_visibility = out_ls.select_by_edge_types = out_ls.select_by_collection = True
    out_ls.visibility = "VISIBLE"
    for k in ("select_silhouette", "select_border", "select_crease", "select_edge_mark"):
        setattr(out_ls, k, False)
    out_ls.select_external_contour = True
    out_ls.select_contour = True          # external contour alone can come out empty
    out_ls.collection = cast
    out_ls.collection_negation = "INCLUSIVE"
    out_ls.linestyle.color = (0.0, 0.0, 0.0)
    out_ls.linestyle.thickness = float(cfg["cast"]["outline"])
