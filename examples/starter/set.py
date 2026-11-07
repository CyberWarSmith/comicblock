"""The starter set: a small study, 5.0 x 4.2 m, ceiling 2.8 m. Built by `comicblock build` with the kit
(comicblock/bl/kit.py). Plan (metres, +y north):

    north wall (y 4.2): door at x 3.9 to the hall
    east wall  (x 5.0): window at y 2.0, desk under it, chair facing the window
    west wall  (x 0.0): bookshelves
    south wall (y 0.0): the FOURTH WALL (4W_Study): hidden unless a camera turns round; sideboard and a picture on it
    centre: rug, armchair, floor lamp; a small chandelier over the rug

Keep sets plain (flat colours, no textures); the image model supplies the finish. Every feature named in
project.yaml (set.features) needs real geometry here, or the model invents one.
"""

W, D, H = 5.0, 4.2, 2.8
DOOR_X = 3.9
WIN_Y = 2.0


def build(kit):
    walls = kit.shell("Study", 0.0, W, 0.0, D, H, wall="wall", floor="floor", ceiling="oak", fourth=("S",))
    kit.door("Door", walls["N"], "N", DOOR_X, width=0.95, spring=2.05, apex=2.05, hinge=1)
    # the hall beyond the door, so an open door shows something
    kit.box("HallFloor", (DOOR_X - 1.0, D + 0.2, -0.1), (DOOR_X + 1.0, D + 2.2, 0.0), "stone")
    kit.box("HallBack", (DOOR_X - 1.0, D + 2.2, 0), (DOOR_X + 1.0, D + 2.4, 2.6), "plaster")
    kit.window("Window", walls["E"], "E", WIN_Y, width=1.1, sill=0.95, spring=2.05, apex=2.45)

    # desk under the window, chair facing it (a sitter faces east)
    kit.table("Desk", 4.30, 4.95, 1.30, 2.70, 0.75, "wood")
    kit.box("DeskLamp", (4.75, 2.40, 0.75), (4.85, 2.50, 1.10), "brass")
    kit.box("DeskBooks", (4.50, 1.45, 0.75), (4.80, 1.75, 0.85), "book")
    kit.chair("DeskChair", (3.95, 2.00), face="E", seat=0.45)

    # bookshelves along the west wall
    kit.shelves("Shelves", 0.0, 0.35, 0.6, 3.4, 2.1, n=5, facing="E")

    # armchair, rug, floor lamp
    kit.box("Rug", (1.0, 1.2, 0.0), (3.2, 3.2, 0.012), "rug")
    kit.box("ArmchairBase", (1.2, 2.9, 0.08), (2.0, 3.7, 0.42), "leather")
    kit.box("ArmchairBack", (1.2, 3.5, 0.42), (2.0, 3.7, 1.00), "leather")
    kit.box("ArmchairArmL", (1.2, 2.9, 0.42), (1.35, 3.7, 0.65), "leather")
    kit.box("ArmchairArmR", (1.85, 2.9, 0.42), (2.0, 3.7, 0.65), "leather")
    kit.cyl("LampBase", (0.75, 3.75, 0.0), 0.15, 0.03, kit.m("dark"))
    kit.cyl("LampStem", (0.75, 3.75, 0.03), 0.015, 1.45, kit.m("dark"))
    kit.cyl("LampShade", (0.75, 3.75, 1.45), 0.22, 0.28, kit.m("cream"), r2=0.12)
    kit.light("LampLight", "POINT", (0.75, 3.75, 1.5), 120, radius=0.2)
    kit.chandelier("Ch", (2.3, 2.2, 2.35), 5, 0.30, ceiling=H)
    kit.light("Fill", "SUN", (2.5, 0.0, 4.0), 1.6, colour=(1.0, 0.88, 0.75), rot=(0.95, 0.0, 0.35))

    # fourth-wall dressing (named 4W_Study_* so it hides with the wall)
    kit.box("4W_Study_Sideboard", (1.4, 0.0, 0.10), (3.4, 0.48, 0.90), "wood")
    kit.box("4W_Study_Picture", (1.9, 0.0, 1.35), (2.9, 0.04, 2.05), "brass")
