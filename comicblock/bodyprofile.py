"""Body measurement by horizontal cross-sections of a standing figure (z up, feet at z = 0). Pure numpy, so the
same code measures an OBJ outside Blender and the MPFB body inside it.

Torso slices (0.40-0.72 of height): occupied width (x) and depth (y). Leg slices (0.08-0.36): mean width/depth of
one leg. Arms are excluded (on MPFB by nearest-bone labels; on the target, use a T- or A-pose so they're clear of
the torso slices). Heads are not fitted: hair makes them unmeasurable.
"""
import json

import numpy as np

TORSO = np.round(np.arange(0.40, 0.725, 0.02), 3)
LEGS = np.round(np.arange(0.08, 0.365, 0.04), 3)


def section(co, tri, h):
    z = co[tri, 2] - h
    cut = (z.min(axis=1) < 0) & (z.max(axis=1) > 0)
    if cut.sum() < 6:
        return None
    t, z = tri[cut], z[cut]
    pts = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b, za, zb = co[t[:, i]], co[t[:, j]], z[:, i], z[:, j]
        c = za * zb < 0
        p = np.full((len(t), 3), np.nan)
        p[c] = a[c] + (b[c] - a[c]) * (za[c] / (za[c] - zb[c]))[:, None]
        pts.append(p)
    pts = np.stack(pts, axis=1)
    order = np.argsort(np.isnan(pts[:, :, 0]), axis=1, kind="stable")[:, :2]
    return np.take_along_axis(pts, order[:, :, None], axis=1)


def covered(seg):
    """Width along x occupied by the outline (union of segment x-spans): gaps between legs are not counted."""
    lo, hi = seg[:, :, 0].min(axis=1), seg[:, :, 0].max(axis=1)
    o = np.argsort(lo); lo, hi = lo[o], hi[o]
    total, cur_lo, cur_hi = 0.0, lo[0], hi[0]
    for a, b in zip(lo[1:], hi[1:]):
        if a > cur_hi + 0.004:
            total += cur_hi - cur_lo; cur_lo, cur_hi = a, b
        else:
            cur_hi = max(cur_hi, b)
    return float(total + cur_hi - cur_lo)


def profile(co, tri, keep=None, H=None):
    co = co.copy()
    if keep is None:
        keep = np.ones(len(co), bool)
    co[:, 2] -= co[keep, 2].min()
    Hm = co[keep, 2].max()
    s = (H / Hm) if H else 1.0
    co *= s
    Hn = Hm * s
    co[:, 0] -= np.median(co[keep, 0])
    tri = tri[keep[tri].all(axis=1)]
    out = {}
    for f in TORSO:
        sec = section(co, tri, f * Hn)
        if sec is not None:
            out[("t", float(f))] = (covered(sec), float(np.ptp(sec[:, :, 1])))
    for f in LEGS:
        sec = section(co, tri, f * Hn)
        if sec is None:
            continue
        cx = sec[:, :, 0].mean(axis=1)
        L, R = sec[cx < 0], sec[cx > 0]
        if len(L) < 3 or len(R) < 3:
            continue
        out[("l", float(f))] = ((covered(L) + covered(R)) / 2, (float(np.ptp(L[:, :, 1])) + float(np.ptp(R[:, :, 1]))) / 2)
    return Hn, out


def error(prof, target):
    """RMS relative width/depth mismatch over the shared slices (each term clipped so one stray limb can't dominate)."""
    r = []
    for k, (w, d) in target.items():
        if k in prof:
            pw, pd = prof[k]
            r += [float(np.clip(pw / w - 1, -0.8, 0.8)), float(np.clip(pd / d - 1, -0.8, 0.8))]
    return float(np.sqrt(np.mean(np.square(r)))) if r else 9.0


def load_obj(path, up="y"):
    """Vertices and triangles from an OBJ (fan-triangulated). up="y" converts a Y-up export to Z-up."""
    vs, tris = [], []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("v "):
                vs.append([float(x) for x in line.split()[1:4]])
            elif line.startswith("f "):
                idx = [int(p.split("/")[0]) for p in line.split()[1:]]
                idx = [i - 1 if i > 0 else len(vs) + i for i in idx]
                tris += [(idx[0], idx[k], idx[k + 1]) for k in range(1, len(idx) - 1)]
    co = np.array(vs, float)
    if up == "y":
        co = np.stack([co[:, 0], -co[:, 2], co[:, 1]], axis=1)
    return co, np.array(tris, np.int64)


def profile_obj(path, height, up="y"):
    co, tri = load_obj(path, up)
    return profile(co, tri, H=height)[1]


def save_targets(prof, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"%s%.3f" % k: list(v) for k, v in prof.items()}, fh, indent=1)


def load_targets(path):
    with open(path, encoding="utf-8") as fh:
        return {(k[0], float(k[1:])): tuple(v) for k, v in json.load(fh).items()}
