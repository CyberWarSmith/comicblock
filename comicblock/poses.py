"""Pose building blocks for panel specs (pure Python: panels.py imports these in Blender and outside it).

A pose is a dict in the character's REST FRAME: the character faces -Y, their own left is +X, metres, floor z = 0.
Keys (all optional except root):
    root            hip drop in metres (0 standing; ~0.43 kneeling). Or `sit`: seat height, and root is derived.
    hip_shift       (x, y) shift of the hips
    chest_lift      degrees; + leans the chest back, - leans forward
    turn            head yaw in degrees, + toward the character's own LEFT (split neck 40% / head 60%)
    tilt            head pitch in degrees, + tips the head DOWN, - chin up
    <side>_<part>_ik  IK target positions: left/right x hand/elbow/foot/knee. z None on a foot = planted.
    left_grip / right_grip  finger curl in degrees (0 open, ~25 relaxed, ~70 a fist or a grip on a prop)

Gaze follows the HEAD, not the eyes: image models ignore the eye-aim. Turn and tilt the head toward the target.
Keep gesturing hands clear of the body silhouette: a hand in front of the torso vanishes in the render.
Unset hands stay in MPFB's rest A-pose (arms angled out), so the base poses below set loose arms.
"""

RELAXED = dict(left_grip=25, right_grip=25)

STAND = dict(root=0.0, left_foot_ik=(0.12, 0.0, None), right_foot_ik=(-0.12, 0.02, None), **RELAXED,
             left_hand_ik=(0.24, 0.03, 0.84), right_hand_ik=(-0.24, 0.03, 0.84),
             left_elbow_ik=(0.30, 0.35, 1.10), right_elbow_ik=(-0.30, 0.35, 1.10))

SIT = dict(sit=0.48, left_foot_ik=(0.14, -0.50, None), right_foot_ik=(-0.14, -0.48, None),
           left_knee_ik=(0.15, -0.95, 0.55), right_knee_ik=(-0.15, -0.95, 0.55), **RELAXED,
           left_hand_ik=(0.15, -0.42, 0.60), right_hand_ik=(-0.15, -0.42, 0.60),
           left_elbow_ik=(0.32, -0.10, 0.80), right_elbow_ik=(-0.32, -0.10, 0.80))

KNEEL_R = dict(root=0.43, right_foot_ik=(-0.11, 0.42, 0.06), right_knee_ik=(-0.12, -0.40, 0.05),
               left_foot_ik=(0.13, -0.46, None), left_knee_ik=(0.16, -0.95, 0.55), **RELAXED)


def P(base, **kw):
    """A copy of a pose with some keys changed: P(STAND, turn=30, tilt=10)."""
    d = dict(base)
    d.update(kw)
    return d


def hands(l, r, le=None, re=None):
    """Hand IK targets (left, right) plus elbow targets; elbows default to out, back and a little up."""
    out = dict(left_hand_ik=tuple(l), right_hand_ik=tuple(r))
    out["left_elbow_ik"] = tuple(le) if le else (l[0] + 0.20, l[1] + 0.25, l[2] + 0.10)
    out["right_elbow_ik"] = tuple(re) if re else (r[0] - 0.20, r[1] + 0.25, r[2] + 0.10)
    return out


# Hand sets measured on a ~1.65-1.80 m figure. Seated sets assume SIT.
ARMS_LOOSE = hands((0.24, 0.03, 0.84), (-0.24, 0.03, 0.84), (0.30, 0.35, 1.10), (-0.30, 0.35, 1.10))
ARMS_CROSSED = hands((-0.14, -0.20, 1.08), (0.14, -0.18, 1.04), (0.28, -0.12, 1.02), (-0.28, -0.12, 1.02))
BEHIND_BACK = hands((0.08, 0.17, 0.92), (-0.08, 0.17, 0.92), (0.26, 0.22, 1.05), (-0.26, 0.22, 1.05))
HANDS_ON_HIPS = hands((0.18, -0.02, 0.98), (-0.18, -0.02, 0.98), (0.45, 0.05, 1.10), (-0.45, 0.05, 1.10))
ON_KNEES = hands((0.15, -0.42, 0.60), (-0.15, -0.42, 0.60), (0.32, -0.10, 0.80), (-0.32, -0.10, 0.80))
CLASPED = hands((0.05, -0.42, 0.56), (-0.05, -0.42, 0.56), (0.26, -0.25, 0.70), (-0.26, -0.25, 0.70))
SHRUG = hands((0.46, -0.20, 0.98), (-0.46, -0.20, 0.98), (0.36, 0.05, 0.78), (-0.36, 0.05, 0.78))
