"""Optional: fit an MPFB body's shape to a target body (e.g. a T-pose model of the character design from an image-to-3D tool) by comparing
horizontal cross-sections (runs inside Blender; launched by `comicblock fit`).

Coordinate descent over MPFB shape targets (signed: + loads <stem>-incr, - loads <stem>-decr) and the weight and
muscle macros, then the height macro is refit so the visible body keeps its true height. Writes cast/<key>.fit.json,
which `comicblock build` applies on top of project.yaml. Aim for silhouette, not detail; heads are not fitted.
"""
import json
import os

import bpy
import numpy as np

from comicblock import bodyprofile as bp

from . import cast as C

PARAMS = [  # (label, [target stems]); both sides set together
    ("torso width", ["torso-scale-horiz"]), ("torso depth", ["torso-scale-depth"]),
    ("shoulders", ["measure-shoulder-dist"]), ("waist", ["measure-waist-circ"]),
    ("hip width", ["hip-scale-horiz"]), ("hip depth", ["hip-scale-depth"]),
    ("thigh width", ["l-upperleg-scale-horiz", "r-upperleg-scale-horiz"]),
    ("thigh depth", ["l-upperleg-scale-depth", "r-upperleg-scale-depth"]),
    ("calf width", ["l-lowerleg-scale-horiz", "r-lowerleg-scale-horiz"]),
    ("calf depth", ["l-lowerleg-scale-depth", "r-lowerleg-scale-depth"]),
    ("hip size", ["measure-hips-circ"]), ("thigh size", ["measure-thigh-circ"]),
    ("knee size", ["measure-knee-circ"]), ("calf size", ["measure-calf-circ"]),
    ("bust size", ["measure-bust-circ"]), ("thigh fat", ["l-upperleg-fat", "r-upperleg-fat"]),
]
MACROS = [("weight", (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6)), ("muscle", (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6))]


def _segd(p, a, b):
    ab = b - a
    t = np.clip(((p - a) @ ab) / (ab @ ab), 0, 1)
    return np.linalg.norm(p - (a + t[:, None] * ab), axis=1)


def _arm_labels(base, grp):
    """Vertices nearer an arm bone than a torso or leg bone, from MPFB's joint groups (indices are stable)."""
    J = lambda name: base[grp(name)].mean(axis=0)
    chain = lambda names: [(J(a), J(b)) for a, b in zip(names, names[1:])]
    other = chain(["joint-pelvis", "joint-spine-1", "joint-spine-2", "joint-spine-3", "joint-spine-4",
                   "joint-neck", "joint-head", "joint-head-2"])
    arm = []
    for s in "lr":
        other += chain(["joint-neck", "joint-%s-clavicle" % s, "joint-%s-shoulder" % s])
        other += chain(["joint-pelvis", "joint-%s-upper-leg" % s, "joint-%s-knee" % s, "joint-%s-ankle" % s,
                        "joint-%s-foot-2" % s])
        hand, elbow = J("joint-%s-hand" % s), J("joint-%s-elbow" % s)
        arm += chain(["joint-%s-shoulder" % s, "joint-%s-elbow" % s, "joint-%s-hand" % s])
        arm.append((hand, hand + (hand - elbow) * 0.7))
    da = np.minimum.reduce([_segd(base, a, b) for a, b in arm])
    do = np.minimum.reduce([_segd(base, a, b) for a, b in other])
    return da < do


class Fitter:
    def __init__(self, obj, height, target):
        self.o, self.H, self.target = obj, height, target
        kb = obj.data.shape_keys.key_blocks
        n = len(obj.data.vertices)
        base = np.empty(n * 3); kb[0].data.foreach_get("co", base)
        self.base = base.reshape(-1, 3)
        gi = {vg.name: vg.index for vg in obj.vertex_groups}
        member = {}
        for v in obj.data.vertices:
            for g in v.groups:
                member.setdefault(g.group, []).append(v.index)
        grp = lambda name: np.array(member.get(gi[name], []), dtype=np.int64)
        keep = np.zeros(n, bool); keep[grp("body")] = True
        self.keep = keep & ~_arm_labels(self.base, grp)
        obj.data.calc_loop_triangles()
        tri = np.empty(len(obj.data.loop_triangles) * 3, dtype=np.int64)
        obj.data.loop_triangles.foreach_get("vertices", tri)
        self.tri = tri.reshape(-1, 3)

    def mixed(self):
        kb = self.o.data.shape_keys.key_blocks
        co = self.base.copy()
        n = len(co)
        for k in kb[1:]:
            if k.mute or k.value == 0:
                continue
            c = np.empty(n * 3); k.data.foreach_get("co", c)
            co += k.value * (c.reshape(-1, 3) - self.base)
        return co

    def cost(self):
        return bp.error(bp.profile(self.mixed(), self.tri, self.keep, H=self.H)[1], self.target)


def run(cfg, key, targets_path):
    ch = cfg["characters"][key]
    target = bp.load_targets(targets_path)
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    obj, _ = C.create_human(key, dict(ch, mpfb={"macros": (ch.get("mpfb") or {}).get("macros", {})}),
                            dict(cfg, root=os.path.join(cfg["root"], "__nofit__")), rigged=False)
    HP = C._svc("entities.objectproperties").HumanObjectProperties
    F = Fitter(obj, float(ch["height"]), target)
    kb = obj.data.shape_keys.key_blocks
    val = lambda name: kb[name].value if name in kb else 0.0
    state = {label: round(val(st[0] + "-incr") - val(st[0] + "-decr"), 3) for label, st in PARAMS}
    macro = {name: HP.get_value(name, entity_reference=obj) for name, _ in MACROS}
    start = best = F.cost()
    for grid in ((-1, -0.5, 0, 0.5, 1), None):
        for name, values in MACROS:
            for v in (values if grid else [min(max(macro[name] + d, 0), 1) for d in (-0.05, 0.05)]):
                C.set_macro(obj, name, v); c = F.cost()
                if c < best - 1e-4:
                    best, macro[name] = c, v
            C.set_macro(obj, name, macro[name])
        for label, stems in PARAMS:
            cur = state[label]
            for v in (grid if grid else [max(min(cur + d, 1), -1) for d in (-0.25, 0.25)]):
                for s in stems:
                    C.set_target(obj, s, v)
                c = F.cost()
                if c < best - 1e-4:
                    best, state[label] = c, v
            for s in stems:
                C.set_target(obj, s, state[label])
        print("CB fit round: error %.3f" % best)
    targets = {s: state[label] for label, stems in PARAMS for s in stems if state[label]}
    macros = dict((ch.get("mpfb") or {}).get("macros", {}))
    macros.update({k: round(v, 3) for k, v in macro.items()})
    out = C.fit_file(cfg, key)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(dict(macros=macros, targets=targets, error=round(best, 4), start_error=round(start, 4)), fh, indent=1)
    return dict(start=start, error=best, file=out)
