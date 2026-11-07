"""Set-building kit (runs inside Blender). A project's set.py gets this module as `kit` and builds its room with it.

Conventions: metres, z up, floor at z = 0. +y is "north". Everything goes in the ROOM collection.
Materials are flat toon colours (EEVEE); the look comes from the image model, so keep sets plain: shapes, flat
colours and ink lines only. Name the wall(s) the camera normally looks through as fourth walls (4W_<tag>), with any
dressing on them named 4W_<tag>_*, so they hide unless a panel turns round to look at them.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOM = "ROOM"
PALETTE = {
    "wall": (0.55, 0.50, 0.42), "plaster": (0.55, 0.50, 0.42), "floor": (0.26, 0.17, 0.10),
    "wood": (0.30, 0.18, 0.09), "oak": (0.22, 0.13, 0.07), "stone": (0.42, 0.38, 0.32), "dark": (0.03, 0.03, 0.03),
    "metal": (0.62, 0.62, 0.64), "brass": (0.80, 0.60, 0.25), "cream": (0.85, 0.80, 0.68),
    "fabric": (0.30, 0.20, 0.25), "leather": (0.09, 0.17, 0.11), "rug": (0.42, 0.08, 0.07),
    "curtain": (0.45, 0.06, 0.08), "book": (0.40, 0.12, 0.10), "glass": (0.05, 0.08, 0.20), "white": (0.90, 0.90, 0.88),
    "bag": (0.06, 0.06, 0.06), "prop": (0.50, 0.42, 0.30),
}


def set_palette(extra):
    for k, v in (extra or {}).items():
        PALETTE[k] = tuple(v)


# ------------------------------------------------------------------ collections and materials

def coll(name=ROOM, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def toon(name, base):
    """Three-band toon material (EEVEE: diffuse -> Shader to RGB -> constant ramp -> emission)."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    s2 = nt.nodes.new("ShaderNodeShaderToRGB"); ramp = nt.nodes.new("ShaderNodeValToRGB")
    emit = nt.nodes.new("ShaderNodeEmission")
    cr = ramp.color_ramp; cr.interpolation = "CONSTANT"
    cr.elements[0].position = 0.0; cr.elements[0].color = tuple(c * 0.45 for c in base) + (1,)
    cr.elements[1].position = 0.06; cr.elements[1].color = tuple(c * 0.75 for c in base) + (1,)
    cr.elements.new(0.22).color = tuple(base) + (1,)
    for a, b in ((diff, s2), (s2, ramp), (ramp, emit)):
        nt.links.new(a.outputs[0], b.inputs[0])
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    m.diffuse_color = tuple(base) + (1,)
    return m


def flat(name, colour, strength=1.0):
    """Unlit flat colour (emission). Also used for glowing things: fire, bulbs, night glass."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission"); o = nt.nodes.new("ShaderNodeOutputMaterial")
    e.inputs["Color"].default_value = tuple(colour) + (1,)
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], o.inputs["Surface"])
    m.diffuse_color = tuple(colour) + (1,)
    return m


def m(key):
    """Palette material by name: m("oak"). Unknown names fail loudly so typos don't render grey."""
    if key not in PALETTE:
        raise KeyError("No colour %r in the palette; add it under set.palette in project.yaml" % key)
    return toon("CB_" + key, PALETTE[key])


# ------------------------------------------------------------------ primitives

def _link(o, collection):
    (collection or coll()).objects.link(o)
    return o


def _mesh_obj(name, bm, mat, collection=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mat if not isinstance(mat, str) else m(mat))
    return _link(o, collection)


def box(name, lo, hi, mat, collection=None):
    """Axis-aligned box from corner lo (x, y, z) to corner hi."""
    bm = bmesh.new()
    c = [(a + b) / 2 for a, b in zip(lo, hi)]
    s = [b - a for a, b in zip(lo, hi)]
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(c) @ Matrix.Diagonal((*s, 1)))
    return _mesh_obj(name, bm, mat, collection)


def cyl(name, at, r, h, mat, seg=20, collection=None, r2=None):
    """Upright cylinder (or cone with r2) standing on `at`."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h,
                          matrix=Matrix.Translation((at[0], at[1], at[2] + h / 2)))
    return _mesh_obj(name, bm, mat, collection)


def sphere(name, at, r, mat, collection=None):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=12, radius=r, matrix=Matrix.Translation(at))
    return _mesh_obj(name, bm, mat, collection)


def segment(bm, a, b, r0, r1, seg=10):
    """Add a tapered rod from a to b to a bmesh (arms, handles, chains)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    mt = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r0, radius2=r1, depth=d.length, matrix=mt)


def rod(name, a, b, r, mat, collection=None):
    bm = bmesh.new(); segment(bm, a, b, r, r, 8)
    return _mesh_obj(name, bm, mat, collection)


def _arch_profile(cx, width, z0, spring, apex, seg=8):
    hw = width / 2
    pts = [(cx - hw, z0), (cx + hw, z0), (cx + hw, spring)]
    for i in range(1, seg + 1):
        a = i / seg * math.pi / 3
        x = cx + hw - width * (1 - math.cos(a))
        z = spring + (apex - spring) * math.sin(a) / math.sin(math.pi / 3)
        pts.append((min(x, cx + hw), z) if x > cx else (cx, apex))
    pts[-1] = (cx, apex)
    pts += [(2 * cx - x, z) for x, z in reversed(pts[3:-1])] + [(cx - hw, spring)]
    return pts


def arch(name, centre, width, z0, spring, apex, d0, d1, mat, axis="y", collection=None):
    """A solid pointed-arch prism: an opening, door leaf, window glass or cutter.
    axis="y": the wall runs along X (a north or south wall); the arch is centred at x=centre, extruded y d0..d1.
    axis="x": the wall runs along Y (an east or west wall); centred at y=centre, extruded x d0..d1.
    spring == apex gives a square-headed opening."""
    pts = _arch_profile(0.0, width, z0, spring, apex) if apex > spring + 1e-6 else \
        [(-width / 2, z0), (width / 2, z0), (width / 2, apex), (-width / 2, apex)]

    def v(u, d, z):                                    # u across the wall, d through it
        return (centre + u, d, z) if axis == "y" else (d, centre + u, z)
    bm = bmesh.new()
    fr = [bm.verts.new(v(u, d0, z)) for u, z in pts]
    bk = [bm.verts.new(v(u, d1, z)) for u, z in pts]
    bm.faces.new(fr); bm.faces.new(list(reversed(bk)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((fr[i], fr[j], bk[j], bk[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _mesh_obj(name, bm, mat, collection)


def cut(target, cutter):
    """Boolean-subtract cutter from target (applied), then delete the cutter."""
    mod = target.modifiers.new("cut", "BOOLEAN"); mod.operation = "DIFFERENCE"; mod.object = cutter
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    with bpy.context.temp_override(object=target, active_object=target):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter)


def light(name, kind, at, energy, colour=(1.0, 0.75, 0.45), radius=0.1, rot=None, collection=None):
    ld = bpy.data.lights.new(name, kind); ld.energy = energy; ld.color = colour
    if kind != "SUN":
        ld.shadow_soft_size = radius
    o = bpy.data.objects.new(name, ld); o.location = at
    if rot:
        o.rotation_euler = rot
    return _link(o, collection)


def pivot(name, at, children, collection=None):
    """An empty at `at` that the children are parented to (door hinges, lids)."""
    p = _link(bpy.data.objects.new(name, None), collection)
    p.location = at
    bpy.context.view_layer.update()
    for o in children:
        o.parent = p
        o.matrix_parent_inverse = p.matrix_world.inverted()
    return p


def legs4(name, x0, x1, y0, y1, h, mat, r=0.025, inset=0.04):
    pts = ((x0 + inset, y0 + inset), (x1 - inset, y0 + inset), (x0 + inset, y1 - inset), (x1 - inset, y1 - inset))
    return [box("%s%d" % (name, i), (x - r, y - r, 0), (x + r, y + r, h), mat) for i, (x, y) in enumerate(pts)]


def table(name, x0, x1, y0, y1, h, mat="wood"):
    top = box(name + "Top", (x0, y0, h - 0.05), (x1, y1, h), mat)
    return [top] + legs4(name + "Leg", x0, x1, y0, y1, h - 0.05, mat, r=0.03, inset=0.05)


def chair(name, at, face="S", seat=0.45, mat="wood"):
    """Simple chair; `face` is the compass direction a sitter faces (N, S, E, W)."""
    cx, cy = at
    s = 0.22
    yaw = {"S": 0, "N": 180, "E": 90, "W": -90}[face]
    objs = [box(name + "Seat", (cx - s, cy - s, seat - 0.05), (cx + s, cy + s, seat), mat),
            box(name + "Back", (cx - s, cy + s - 0.05, seat), (cx + s, cy + s, seat + 0.5), mat)]
    objs += legs4(name + "Leg", cx - s, cx + s, cy - s, cy + s, seat - 0.05, mat, r=0.02, inset=0.03)
    p = pivot(name + "Pivot", (cx, cy, 0), objs)
    p.rotation_euler = (0, 0, math.radians(yaw))
    bpy.context.view_layer.update()
    return p


def shelves(name, x0, x1, y0, y1, h, n=4, mat="wood", books=True, facing="E"):
    """Open shelving unit, open toward `facing` (the compass side the shelves face), books as blocks."""
    objs = [box(name, (x0, y0, 0), (x1, y1, h), mat)]
    along_x = facing in ("N", "S")                       # the unit runs along X when it faces north or south
    t, back = 0.04, 0.03
    lo = [x0 + t, y0 + t, 0.08] if along_x else [x0, y0 + t, 0.08]
    hi = [x1 - t, y1 - t, h - 0.06] if along_x else [x1, y1 - t, h - 0.06]
    if facing == "E":
        lo[0], hi[0] = x0 + back, x1 + 0.05
    elif facing == "W":
        lo[0], hi[0] = x0 - 0.05, x1 - back
    elif facing == "N":
        lo[1], hi[1] = y0 + back, y1 + 0.05
    else:
        lo[1], hi[1] = y0 - 0.05, y1 - back
    cut(objs[0], box("c", tuple(lo), tuple(hi), "dark"))
    for i in range(n):
        z = 0.08 + i * (h - 0.14) / n
        objs.append(box("%sShelf%d" % (name, i), (x0, y0, z), (x1, y1, z + 0.025), mat))
        if books:
            span = (x1 - x0 if along_x else y1 - y0) - 0.12
            for j in range(int(span / 0.12)):
                a = (x0 if along_x else y0) + 0.06 + j * 0.12
                bh = min(0.20 + 0.04 * (j % 3), (h - 0.14) / n - 0.05)
                if along_x:
                    blo, bhi = (a, y0 + back + 0.02, z + 0.025), (a + 0.09, y1 - 0.04, z + 0.025 + bh)
                else:
                    blo, bhi = (x0 + back + 0.02, a, z + 0.025), (x1 - 0.04, a + 0.09, z + 0.025 + bh)
                objs.append(box("%sBook%d_%d" % (name, i, j), blo, bhi, "book"))
    return objs


def chandelier(name, at, arms, radius, ceiling, mat_key="brass", bulb=(1.0, 0.80, 0.45)):
    """Hanging fixture: chain, hub, arms with sleeves and glowing bulbs, plus a point light."""
    ch = Vector(at)
    objs = [cyl(name + "Chain", (ch.x, ch.y, ch.z + 0.1), 0.01, ceiling - ch.z - 0.1, m("dark")),
            cyl(name + "Hub", (ch.x, ch.y, ch.z - 0.12), 0.06, 0.25, m(mat_key))]
    glow = flat("CB_bulb", bulb, 8.0)
    for i in range(arms):
        a = i * 2 * math.pi / arms
        p = (ch.x + radius * math.cos(a), ch.y + radius * math.sin(a))
        objs.append(rod("%sArm%d" % (name, i), (ch.x, ch.y, ch.z - 0.05), (p[0], p[1], ch.z), 0.012, m(mat_key)))
        objs.append(cyl("%sCup%d" % (name, i), (p[0], p[1], ch.z), 0.04, 0.03, m(mat_key)))
        objs.append(cyl("%sSleeve%d" % (name, i), (p[0], p[1], ch.z + 0.03), 0.016, 0.09, m("cream")))
        objs.append(cyl("%sBulb%d" % (name, i), (p[0], p[1], ch.z + 0.12), 0.028, 0.06, glow, seg=10, r2=0.012))
    objs.append(light(name + "Light", "POINT", (ch.x, ch.y, ch.z + 0.1), 220, colour=(1.0, 0.75, 0.45), radius=0.4))
    return objs


# ------------------------------------------------------------------ rooms

WALL_T = 0.2


def shell(tag, x0, x1, y0, y1, h, wall="wall", floor="floor", ceiling="oak", fourth=("S",), boards=0.22, beams=True):
    """A room: floor (with board seams), ceiling (+ beams), four walls. Walls listed in `fourth` are named
    4W_<tag>[_<side>] and hidden by default (the sitcom fourth wall). Returns {"N"|"S"|"E"|"W": wall object}."""
    t = WALL_T
    box(tag + "Floor", (x0, y0, -0.1), (x1, y1, 0.0), floor)
    if boards:
        for i in range(1, int((y1 - y0) / boards)):
            y = y0 + i * boards
            box("%sBoard%d" % (tag, i), (x0, y, -0.004), (x1, y + 0.006, 0.002), "dark")
    box(tag + "Ceiling", (x0 - t, y0 - t, h), (x1 + t, y1 + t, h + 0.1), ceiling)
    if beams:
        n = max(2, int((x1 - x0) / 1.6))
        for i in range(n):
            x = x0 + (i + 0.5) * (x1 - x0) / n
            box("%sBeam%d" % (tag, i), (x - 0.09, y0, h - 0.22), (x + 0.09, y1, h), ceiling)
    spans = {"W": ((x0 - t, y0 - t, 0), (x0, y1 + t, h)), "E": ((x1, y0 - t, 0), (x1 + t, y1 + t, h)),
             "N": ((x0 - t, y1, 0), (x1 + t, y1 + t, h)), "S": ((x0 - t, y0 - t, 0), (x1 + t, y0, h))}
    walls = {}
    for side, (lo, hi) in spans.items():
        if side in fourth:
            name = "4W_" + tag if len(fourth) == 1 else "4W_%s_%s" % (tag, side)
        else:
            name = "%sWall%s" % (tag, side)
        walls[side] = box(name, lo, hi, wall)
    return walls


def _wall_axis(side):
    return "y" if side in ("N", "S") else "x"


def _wall_plane(wall_obj, side):
    """Inner face coordinate of a wall and the direction into the room (+1/-1) along its normal axis."""
    bb = [wall_obj.matrix_world @ Vector(c) for c in wall_obj.bound_box]
    if side == "N":
        return min(v.y for v in bb), -1
    if side == "S":
        return max(v.y for v in bb), 1
    if side == "E":
        return min(v.x for v in bb), -1
    return max(v.x for v in bb), 1


def opening(wall_obj, side, at, width, sill, spring, apex):
    """Cut an arched (or square, spring == apex) hole through a wall. `at` is the position along the wall."""
    inner, _ = _wall_plane(wall_obj, side)
    d0, d1 = (inner - 0.05, inner + WALL_T + 0.05) if side in ("N", "E") else (inner - WALL_T - 0.05, inner + 0.05)
    cut(wall_obj, arch("cut", at, width, sill, spring, apex, d0, d1, m("dark"), axis=_wall_axis(side)))


def door(name, wall_obj, side, at, width=0.95, spring=1.95, apex=2.35, hinge=1, mat="oak"):
    """A doorway with a leaf on a hinge pivot (<name>Pivot), opening into the room. hinge = +1 / -1 picks the
    jamb (+ toward larger x or y). Open it per panel with doors={"<name>": degrees} in the spec."""
    opening(wall_obj, side, at, width, -0.05, spring, apex)
    inner, into = _wall_plane(wall_obj, side)
    axis = _wall_axis(side)
    leaf = arch(name + "Leaf", at, width - 0.04, 0.0, spring, apex - 0.02, inner + into * 0.01,
                inner + into * 0.07, m(mat), axis=axis)
    knob_u, knob_d = at - hinge * (width / 2 - 0.12), inner + into * 0.09
    knob = cyl(name + "Knob", (knob_u, knob_d, 0.95) if axis == "y" else (knob_d, knob_u, 0.95), 0.03, 0.04, m("brass"))
    knob.parent = leaf
    for s in (-1, 1):                                   # jamb trim either side
        u = at + s * (width / 2 + 0.04)
        lo = (u - 0.06, inner + into * 0.05, 0) if axis == "y" else (inner + into * 0.05, u - 0.06, 0)
        hi = (u + 0.06, inner, spring + 0.1) if axis == "y" else (inner, u + 0.06, spring + 0.1)
        box("%sJamb%d" % (name, s), tuple(map(min, lo, hi)), tuple(map(max, lo, hi)), mat)
    hu = at + hinge * (width / 2 - 0.02)
    at3 = (hu, inner + into * 0.01, 0) if axis == "y" else (inner + into * 0.01, hu, 0)
    p = pivot(name + "Pivot", at3, [leaf])
    p["cb_door_sign"] = -hinge * into * (1 if axis == "y" else -1)   # so positive angles always swing inward
    return p


def window(name, wall_obj, side, at, width=1.0, sill=0.9, spring=2.1, apex=2.6, curtains=True):
    """A window: hole, night glass (flat, slightly glowing), glazing bars, sill, curtains on a rod."""
    opening(wall_obj, side, at, width, sill, spring, apex)
    inner, into = _wall_plane(wall_obj, side)
    axis = _wall_axis(side)
    out = -into                                         # toward the outside

    def B(nm, u0, u1, d0, d1, z0, z1, mat):
        lo = (min(u0, u1), min(d0, d1), z0) if axis == "y" else (min(d0, d1), min(u0, u1), z0)
        hi = (max(u0, u1), max(d0, d1), z1) if axis == "y" else (max(d0, d1), max(u0, u1), z1)
        return box(nm, lo, hi, mat)
    g = inner + out * 0.11
    arch(name + "Glass", at, width, sill, spring, apex, g, g + out * 0.02, flat("CB_night", PALETTE["glass"], 1.0), axis=axis)
    for i in (-1, 0, 1):
        u = at + i * width / 3
        B("%sMull%d" % (name, i), u - 0.012, u + 0.012, inner + out * 0.08, inner + out * 0.10, sill, apex, "dark")
    for k, z in enumerate((sill + (spring - sill) * 0.4, sill + (spring - sill) * 0.8)):
        B("%sTrans%d" % (name, k), at - width / 2, at + width / 2, inner + out * 0.08, inner + out * 0.10, z - 0.012, z + 0.012, "dark")
    B(name + "Sill", at - width / 2 - 0.08, at + width / 2 + 0.08, inner + into * 0.08, inner + out * 0.10, sill - 0.05, sill, "stone")
    if curtains:
        B(name + "Rod", at - width / 2 - 0.45, at + width / 2 + 0.45, inner + into * 0.11, inner + into * 0.14, apex + 0.12, apex + 0.15, "brass")
        for s in (-1, 1):
            u0, u1 = at + s * (width / 2 + 0.05), at + s * (width / 2 + 0.45)
            B("%sCurtain%d" % (name, s), u0, u1, inner + into * 0.06, inner + into * 0.18, 0.15, apex + 0.12, "curtain")


# ------------------------------------------------------------------ set state (used by staging and plot renders)

def set_doors(angles):
    """{"Door": 70, ...}: open each door pivot (<name>Pivot) by that many degrees (0 = shut)."""
    for o in bpy.data.objects:
        if o.name.endswith("Pivot") and "cb_door_sign" in o:
            ang = angles.get(o.name[:-5], 0)
            o.rotation_euler = (0, 0, math.radians(ang) * o["cb_door_sign"])
    bpy.context.view_layer.update()


def show_fourth(walls=()):
    """Hide every 4W_* object except those whose name starts with one of `walls`."""
    for o in bpy.data.objects:
        if o.name.startswith("4W_"):
            hidden = not any(o.name.startswith(w) for w in walls)
            o.hide_render = hidden
            o.hide_viewport = hidden
    bpy.context.view_layer.update()


def show_hide(show=(), hide=()):
    """Force objects on or off by name prefix (for set states: a lamp on, a box gone). Reset each panel."""
    for o in bpy.data.objects:
        if o.get("cb_forced"):
            o.hide_render = o.hide_viewport = bool(o["cb_forced_was"])
            del o["cb_forced"], o["cb_forced_was"]
    for names, hidden in ((hide, True), (show, False)):
        for o in bpy.data.objects:
            if any(o.name.startswith(n) for n in names):
                if not o.get("cb_forced"):
                    o["cb_forced"] = 1
                    o["cb_forced_was"] = int(o.hide_render)
                o.hide_render = o.hide_viewport = hidden
    bpy.context.view_layer.update()
