"""Starter panels: Ada is working late; Ben comes in. Format: comicblock/panels.py. Poses: comicblock/poses.py.

Continuity: night. Ada sits at the desk under the east window. Ben enters by the north door.
Axis (the 180-degree line): every camera stays on the south-west side of the Ada-Ben line, so Ben is always
screen-left of Ada, and in Ada's close-up (3) she looks screen-left, toward where Ben is.
"""
from comicblock.poses import P, SIT, STAND, hands

ADA_DESK = (3.95, 2.00)          # in the desk chair (seat 0.45), facing the window
BEN_DOOR = (3.85, 3.70)          # just inside the door
ADA_HEAD = (3.95, 2.0, 1.15)     # seated head height, roughly
BEN_HEAD = (3.85, 3.7, 1.70)

PANELS = {
    "1": dict(
        size=(1536, 1024), cam="WIDE", lens=22,
        cast={"ada": dict(at=ADA_DESK, face=(5.0, 2.0), look=(4.6, 1.9, 0.8),
                          pose=P(SIT, sit=0.45, chest_lift=-10, tilt=18,
                                 **hands((0.12, -0.42, 0.80), (-0.12, -0.42, 0.80))))},
        action="Wide establishing shot of the study at night. Ada sits at the desk under the window with her back "
               "half to us, bent over an open book, absorbed. The rest of the room is quiet and dim.",
    ),
    "2": dict(
        size=(1536, 1024), cam="DOOR", dolly=True, doors={"Door": 75}, bottom="knees", pad=(0.10, 0.10, 0.08, 0.04),
        cast={"ben": dict(at=BEN_DOOR, face=(3.2, 1.5), look="ada",
                          pose=P(STAND, turn=35, tilt=12, left_grip=55, left_elbow_ik=(0.40, 0.05, 1.05)),
                          world_ik={"left_hand_ik": (4.18, 3.42, 1.00)}),
              "ada": dict(at=ADA_DESK, face=(5.0, 2.0), look="ben",
                          pose=P(SIT, sit=0.45, turn=75, chest_lift=4,
                                 **hands((0.12, -0.42, 0.80), (-0.12, -0.42, 0.80))))},
        action="Ben leans in through the open door, his hand still on its edge, rain on his coat, with an "
               "apologetic half-smile. Ada twists round in her desk chair to look at him, surprised.",
    ),
    "3": dict(
        size=(1024, 1024), cam=((3.25, 1.20, 1.20), (3.95, 2.00, 1.05)), bottom="chest",
        pad=(0.10, 0.10, 0.12, 0.0),
        cast={"ada": dict(at=ADA_DESK, face=(4.4, 0.9), look=BEN_HEAD,
                          pose=P(SIT, sit=0.45, turn=55, tilt=-12, right_grip=65,
                                 **hands((0.15, -0.42, 0.60), (-0.04, -0.24, 1.02), None, (-0.30, -0.05, 0.85))))},
        props=[{"type": "held", "who": "ada", "hand": "R", "size": (0.15, 0.21, 0.03), "colour": "book"}],
        action="Close on Ada in her desk chair, holding a small closed book against her chest in her right hand, "
               "looking up and off to the left at Ben (off-panel) with a wary, tired frown.",
    ),
}
