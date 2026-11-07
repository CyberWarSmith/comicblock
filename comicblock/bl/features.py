"""Which named set features are in frame (runs inside Blender), so the prompt names only those.

Each feature has world sample points. A feature counts as seen when any point is inside the frame AND a ray from
the camera reaches it (nothing nearer is hit), so a door behind a wall or a fourth-wall feature that is hidden is
not named. Naming features that are not visible makes the model invent them; a generic room description made it
replace a niche with a doorway.
"""
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def seen(sc, dg, p, margin=0.25):
    p = Vector(p)
    c = world_to_camera_view(sc, sc.camera, p)
    if not (c.z > 0 and 0 <= c.x <= 1 and 0 <= c.y <= 1):
        return False
    o = sc.camera.matrix_world.translation
    d = p - o
    hit, *_ = sc.ray_cast(dg, o, d.normalized(), distance=max(d.length - margin, 0.01))
    return not hit


def visible(features, fourth=()):
    """features: {name: {points: [...], text: ..., requires: "4W_..."}} -> names in frame and unoccluded."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for name, f in features.items():
        req = f.get("requires")
        if req and not any(w.startswith(req) or req.startswith(w) for w in fourth):
            continue
        if any(seen(sc, dg, p) for p in f["points"]):
            out.append(name)
    return out


def px(p):
    """Pixel position (x right, y down) of a world point in the current camera."""
    sc = bpy.context.scene
    c = world_to_camera_view(sc, sc.camera, Vector(p))
    return round(c.x * sc.render.resolution_x), round((1 - c.y) * sc.render.resolution_y)
