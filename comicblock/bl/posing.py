"""Pose and place MPFB rigs from the rest-frame pose format in comicblock.poses (runs inside Blender).

Poses are written as IK targets in the rig's REST frame (facing -Y, character's left +X, floor z 0); the rig is then
yawed to face `face` and moved to its floor mark `at`. Every call resets the pose first, so the spec is the source
of truth and re-staging a panel always gives the same result.
"""
import math

import bpy
from mathutils import Matrix, Vector


def reset(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    arm.location, arm.rotation_euler = (0, 0, 0), (0, 0, 0)
    bpy.context.view_layer.update()


def rest_head(arm, bone):
    return arm.data.bones[bone].head_local.copy()


def move_to(arm, bone, target):
    """Put a pose bone's head at `target` (armature space), keeping its current orientation."""
    pb = arm.pose.bones[bone]
    mt = pb.matrix.copy()
    pb.matrix = Matrix.Translation(Vector(target)) @ Matrix(mt.to_3x3()).to_4x4()
    bpy.context.view_layer.update()


def rotate_world(arm, bone, axis, degrees):
    pb = arm.pose.bones[bone]
    mt = pb.matrix.copy()
    r = Matrix.Rotation(math.radians(degrees), 4, axis)
    pb.matrix = Matrix.Translation(mt.translation) @ r @ Matrix(mt.to_3x3()).to_4x4()
    bpy.context.view_layer.update()


def pose(arm, p):
    """Apply a pose dict (see comicblock.poses). `sit` (seat height) sets the hip drop for a seat that high."""
    p = dict(p)
    reset(arm)
    root = rest_head(arm, "root")
    if "sit" in p:                                   # hip joint ~0.10 m above the seat
        p["root"] = root.z - (p.pop("sit") + 0.10)
    sx, sy = p.get("hip_shift", (0.0, 0.0))
    move_to(arm, "root", (root.x + sx, root.y + sy, root.z - p.get("root", 0.0)))
    if p.get("chest_lift"):                          # + lifts the chest back, - leans forward
        rotate_world(arm, "spine03", "X", -p["chest_lift"] * 0.5)
        rotate_world(arm, "spine01", "X", -p["chest_lift"] * 0.5)
    for bone, tgt in p.items():                      # after the spine, so hand targets aren't dragged off by it
        if not bone.endswith("_ik") or bone not in arm.pose.bones:
            continue
        x, y, z = tgt
        if z is None:                                # planted foot: keep the control's rest height
            z = rest_head(arm, bone).z
        move_to(arm, bone, (x, y, z))
    for side in ("left", "right"):                   # finger curl via MPFB's master grip (degrees, + closes)
        g = p.get(side + "_grip")
        bone = side + "_master_grip"
        if g and bone in arm.pose.bones:
            pb = arm.pose.bones[bone]
            pb.rotation_mode = "XYZ"
            pb.rotation_euler = (math.radians(g), 0.0, 0.0)
    if p.get("turn"):                                # + toward the character's own left
        rotate_world(arm, "neck01", "Z", p["turn"] * 0.4)
        rotate_world(arm, "head", "Z", p["turn"] * 0.6)
    if p.get("tilt"):                                # + tips the head down; gaze follows the HEAD
        rotate_world(arm, "neck01", "X", p["tilt"] * 0.4)
        rotate_world(arm, "head", "X", p["tilt"] * 0.6)


def place(arm, at, face, lift=0.0):
    """Floor mark (x, y) and the point the body faces (x, y)."""
    x, y = at
    fx, fy = face
    arm.location = (x, y, lift)
    arm.rotation_euler = (0.0, 0.0, math.atan2(fx - x, -(fy - y)))   # rest front is -Y
    bpy.context.view_layer.update()


def head_world(arm):
    return arm.matrix_world @ arm.pose.bones["head"].tail


def aim_eyes(arm, target_world):
    """Aim the eye_ik target. Image models mostly ignore the eyes: use turn/tilt for the gaze that matters."""
    if "eye_ik" in arm.pose.bones:
        move_to(arm, "eye_ik", arm.matrix_world.inverted() @ Vector(target_world))


def world_ik(arm, targets):
    """Pin IK targets to world positions after placement: a hand on a door, a cup, a shoulder."""
    for bone, wpos in (targets or {}).items():
        move_to(arm, bone, arm.matrix_world.inverted() @ Vector(wpos))


def bone_world(arm, bone, tail=False):
    pb = arm.pose.bones[bone]
    return arm.matrix_world @ (pb.tail if tail else pb.head)
