# The blockout-staging method

This is the procedure for making comic panels whose staging, sets and scale stay consistent across a whole scene.
You stage every panel in 3D, render a crude blockout, and have an image model redraw it in your project's style.

It was proven in production on a 25-page issue (finished Oct 2026), on a second issue's test scene (Nov 2026), and in a
second visual style: grounded noir inks on an exterior set, with a different cast and references made in a different
tool. That style test held 3 of 3 panels.

## Why it works

Image models are good at likeness, costume, style and finish. They are bad at holding a room, a camera and true
scale steady from panel to panel. Blender is the opposite. So each one does only what it is good at:

- **Blender decides structure:** where everything is, how big it is, where the camera is.
- **The image model decides appearance:** who the grey figures are, what they wear, how it is drawn.

The hand-off is one image: the blockout render, passed as the **first** reference, followed by the character
sheets of the people in shot.

The blockout carries only structure. The style comes entirely from the character sheets and the prompt's style
block. A new style means new sheets and a new style block; nothing else changes.

## Requirements of the image model

The model must accept **several reference images** and follow the layout of the first one. GPT Image 2 and 2.5
(Sunburst) on Scenario do. FLUX with a canny ControlNet held the room but lost the likeness, and a text-only
prompt could not hold the layout.

## Stage A: once per project

**A1. Character sheets.** Make one or two approved sheets per character: a full body plus a head or expressions.
They are the only source of likeness and style, so lock them before anything else. Clean them first: paint out
signatures and anything the prompt didn't intend. Genre words pull in genre features ("vampire" adds pointed ears
and grey skin), so describe what should be there instead.

**A2. Cast mannequins.** Each character is an MPFB human at its **true height**, measured on the visible body.
Match each body to its design by eye, or by fitting it to a 3D model of the design (`comicblock fit`). Aim for the
silhouette, not detail. The rig is "Default no toes" with MPFB's IK helpers. The material is **flat grey with dark
eyes** and the ink is an **outer outline only**: shaded, fully inked nude mannequins get refused by content filters,
and refusals still charge. Non-human characters (a skeleton, a severed arm, a monster) get custom proxies built
from primitives. Model the details that decide the reading: nails and knuckles if handedness matters.

**A3. Sets.** Build each recurring location **by script** from a plan, so it can be rebuilt exactly and its states
swapped (a door open, a lamp on). Use flat colours and ink lines only. List the set's named features with sample
points, so the pipeline knows which ones are in frame. Interiors and exteriors both work.

**A4. Camera plot.** Fix a few cameras per set, sitcom style. The camera's **direction and height** keep a scene
coherent. Keep one axis (the 180-degree line) per scene.

## Stage B: per panel

**B1. Write the staging spec.** Record the camera, set state and output size (keep the panel's own shape). For
each character, set the floor mark, facing, pose (hand and foot targets, hip drop, lean, head turn **and tilt**)
and gaze target. Add the props, the framing, and one or two sentences of action.

- **Gaze is set by the head, not the eyes.** The model follows where the mannequin's head points and ignores the
  eye aim. Turn **and tilt** the head toward the target.
- Keep gesturing hands **clear of the body**: a hand in front of the torso vanishes.

**B2. Stage and render.** `comicblock stage` sets the set state and shows only this panel's cast. It poses and
places them, adds props, frames the camera, renders the blockout, and records which set features are in frame,
occlusion-tested.

- Start from the plot camera and **move closer** for medium and close shots (about 35 mm; 50 mm for close-ups;
  never nearer than 1 m to a character).
- **Never crop with a long lens.** A long-lens patch of plain wall makes the model reframe and invent.
- For inserts of a held prop, **hide the cast** in the render, or the model reads the bodies as a back view.

**B3. Check the blockout at full size** before spending anything:

- the figures are distinct and the gestures sit clear of the body
- the feet are on the floor, with no intersections
- the props and set features the beat needs are visible

**B4. Generate.** Send one request per panel, usually with two outputs. The prompt goes in this order:

1. the instruction to redraw the blockout keeping camera, framing, perspective, layout, positions, scale, poses and
   facing exactly, replacing each mannequin with the character from the sheets
2. the action
3. the set features **in frame only**
4. a ban on added doors, openings or props, and on objects in empty hands
5. each character's look in one line
6. the style block, the person count, and "no text"

Carry tone by prohibition (no smirking, no winks). Never describe the joke.

**B4a. When figures were moved by hand,** render the scene as it stands (`comicblock render`). Never restage
over it, because restaging resets the edits.

**B5. Review and pick at full size.** Check the likeness, the poses against the blockout, the left-right order, the
props, invented objects and hands. Pick one. **Restage rather than rerun:** almost every failed rerun traced back
to the blockout, not to chance.

## Known failure modes

| Symptom | Cause | Fix |
| --- | --- | --- |
| A set feature replaced (a doorway where a niche is) | Generic room description in the prompt | Name only the features in frame; forbid adding openings |
| Framing pulled wide, room invented | Long-lens crop with too little context | Move the camera closer; cap the lens at about 50 mm |
| Request refused (still charged) | Shaded, fully inked nude mannequins | Flat grey bodies, outline-only ink |
| Request refused for a costume | A famous superhero costume name | Describe the costume, don't name it |
| Invented prop (a briefcase) | Empty hands | Prompt: hands hold nothing unless shown |
| Characters swapped left to right | Model variance | Two outputs per panel; pick the correct one |
| Wrong handedness on a prop hand | A flat proxy hand doesn't show palm versus back | Model nails and knuckles; state the hand in the prompt |
| Prop close-up drawn as a group shot | Cast bodies fill the foreground | Hide the cast in the render (`hide_cast`) |
| Gesture lost | Hand in front of the body | Place hands out from the silhouette |
| Character looks at the reader or off to the side | Head points forward; only the eyes were aimed | Turn and tilt the head toward the target |
| Wrong hand used (left for right) | A head turned to camera on a side-on body reads as front-facing | Three-quarter head turn; name RIGHT/LEFT and anchor to sheet details |
| People or props added to a hand insert | Character sheets sent with a cast-free insert | Cast-free shots send no sheets (automatic) |
| Duplicated set piece (a second ladder) | Set piece missing from the blockout | Build the real piece so the model draws over it |
| Motion doesn't read | Ghost layers give position, not path | One guide image: the final pose with the motion path drawn on it |

## Costs and limits (Scenario, Oct-Nov 2026)

- **GPT Image 2.5 Sunburst:** about **25 CU per panel** for two outputs. GPT Image 2 was about 95 CU.
- Expect about **1.15x** that for ordinary panels and about **1.7x** for hard ones (hand contact, handedness,
  unusual proxies). Budget 10-15% for reruns.
- **Refusals still charge.**
- **Stop at the first 429 and read it.** Scenario's team plan caps API generation, so a 429 may be that cap
  rather than the hourly rate limit, and retries can lengthen the limit.
- Blockout renders take seconds. The real per-panel cost is your time on the spec (B1) and the review (B5).
- Savings:
  - one output instead of two for close-ups
  - paint over small fixes instead of regenerating
  - restage before rerunning

## When to use it

**Use it** for continuity-critical panels: establishing shots, ensembles, and anything that depends on room
geography, props or relative scale.

**Optional** for close-up acting panels: the blockout adds less there and costs the same.
