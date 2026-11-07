"""Auto-framing (runs inside Blender): fit focal length and lens shift so the posed cast fills the frame.

Rules this encodes (each cost credits to learn):
- Start from a fixed plot camera; for medium and close shots MOVE CLOSER (dolly) rather than zoom.
- Cap the lens (default 50 mm). A long-lens crop of plain wall gives the image model too little room context and
  it reframes and invents. Past the cap the frame widens around the same centre instead.
- Shift, don't tilt, for the crop: verticals stay vertical.
"""
import math

import bpy
import numpy as np
from mathutils import Vector

from . import cast as C

CAM = "CB_CAM"
LEVELS = ("feet", "knees", "thighs", "hips", "chest", "neck")


def body_points(keys, bottom="knees"):
    """World points of the visible bodies of `keys` above a body level (feet keeps everything)."""
    pts = [np.zeros((0, 3))]
    for k in keys:
        arm, b = C.rig(k), C.body(k)
        w = lambda bone: (arm.matrix_world @ arm.pose.bones[bone].head).z
        lvl = {"feet": -1e9, "knees": w("lowerleg01.L"), "thighs": 0.5 * (w("lowerleg01.L") + w("root")),
               "hips": w("root"), "chest": w("spine03"), "neck": w("neck01")}[bottom]
        c = C._visible_co(b)
        pts.append(c[c[:, 2] >= lvl][::3])
    return np.vstack(pts)


def camera():
    cam = bpy.data.objects.get(CAM)
    if cam is None:
        cam = bpy.data.objects.new(CAM, bpy.data.cameras.new(CAM))
        bpy.context.scene.collection.objects.link(cam)
    cam.data.sensor_fit = "AUTO"
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.05
    bpy.context.scene.camera = cam
    return cam


def aim(pos, look, lens, width, height, shift=(0.0, 0.0)):
    cam = camera()
    cam.location = Vector(pos)
    cam.rotation_euler = (Vector(look) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.shift_x, cam.data.shift_y = shift
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = width, height, 100
    bpy.context.view_layer.update()
    return cam


def frame_at(pos, look, width, height, keys, bottom="knees", pad=(0.06, 0.06, 0.08, 0.02), extra=(), max_lens=50.0):
    """Camera at pos looking along (look - pos); lens and shift fitted so the cast above `bottom` (plus the
    `extra` world points) fills the frame with pad = (left, right, top, bottom) fractions."""
    cam = aim(pos, look, 35.0, width, height)
    R = cam.matrix_world.to_3x3().transposed()
    pts = body_points(keys, bottom) if keys else np.zeros((0, 3))
    if len(extra):
        pts = np.vstack([pts, np.array(extra, float)])
    if not len(pts):
        return cam
    d = (pts - np.array(pos)) @ np.array(R).T          # camera space: x right, y up, -z forward
    d = d[d[:, 2] < -0.05]
    u, v = d[:, 0] / -d[:, 2], d[:, 1] / -d[:, 2]
    aspect = height / width
    l, r, t, b = pad
    umin, umax, vmin, vmax = u.min(), u.max(), v.min(), v.max()
    wu, hv = umax - umin, vmax - vmin
    span_u = max(wu / (1 - l - r), hv / (1 - t - b) / aspect)   # full frame width in tan units
    span_v = span_u * aspect
    cu = umin - l * span_u + span_u / 2
    if hv / (1 - t - b) / aspect >= wu / (1 - l - r):    # height-limited: centre the spare width
        cu = (umin + umax) / 2 + (r - l) * span_u / 2
        cv = vmin - b * span_v + span_v / 2
    else:                                              # width-limited: keep the top padding, let the bottom fall
        cv = vmax + t * span_v - span_v / 2
    k = max(width, height) / width                    # AUTO sensor fit spans 36 mm across the longer side
    if 36.0 / (span_u * k) > max_lens:                # widen around the same centre instead of a long-lens crop
        span_u = 36.0 / max_lens / k
    cam.data.lens = 36.0 / (span_u * k)
    cam.data.shift_x = cu / (span_u * k)
    cam.data.shift_y = cv / (span_u * k)
    bpy.context.view_layer.update()
    return cam


def _inside(p, bounds):
    if not bounds:
        return True
    x0, x1, y0, y1 = bounds
    return x0 + 0.15 < p.x < x1 - 0.15 and y0 + 0.15 < p.y < y1 - 0.15


def dolly_frame(pos0, look0, width, height, keys, bottom, pad, extra, max_lens=50.0, target_lens=35.0,
                min_dist=1.0, bounds=None):
    """From a plot camera, move toward the cast (same height and direction) until the fit needs about
    `target_lens`, staying inside `bounds` and at least `min_dist` from every character; then fit."""
    pos0, look0 = Vector(pos0), Vector(look0)
    pts = body_points(keys, bottom)
    centre = Vector(tuple(pts.mean(axis=0)))
    ground = Vector((centre.x, centre.y, pos0.z))
    lo, hi, best = 0.0, 0.9, 0.0
    for _ in range(14):
        t = (lo + hi) / 2
        p = pos0.lerp(ground, t)
        near = min(math.hypot(q[0] - p.x, q[1] - p.y) for q in pts[::20])
        lens = frame_at(p, p + (look0 - pos0), width, height, keys, bottom, pad, extra, 1e9).data.lens
        if not _inside(p, bounds) or near < min_dist or lens < target_lens:
            hi = t
        else:
            best, lo = t, t
    pos = pos0.lerp(ground, best)
    return frame_at(pos, pos + (look0 - pos0), width, height, keys, bottom, pad, extra, max_lens)
