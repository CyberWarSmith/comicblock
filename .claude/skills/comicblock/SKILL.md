---
name: comicblock
description: Make comic panels with the blockout-staging method in this repo. Stage each panel in Blender (set, camera, true scale, poses, props), render a grey-mannequin blockout, and have an image model redraw it from character sheets. Use whenever the user wants to set up a comic project, build a set, add characters, write or change panel staging, render blockouts, generate panels (Scenario or by hand), or review and pick results.
---

# comicblock: blockout-staged comic panels

Blender decides **structure** (set, camera, true scale, poses, props). The image model decides **appearance**
(likeness, costume, style). The hand-off is one image: the blockout, sent as the FIRST reference, followed by the
in-shot characters' sheets. The full method, failure-mode table and costs are in `docs/METHOD.md`. Read it before
writing your first panel specs in a session.

The user is usually an **artist, not a coder**. You write and edit `project.yaml`, `set.py` and `panels.py` for
them, run the commands, and show them the images. Explain in plain words, and never ask them to edit Python.

## Commands (run from the repo root; the project is a folder)

```
python -m comicblock doctor   <project>                    # check Blender, MPFB, packages, sheets, credentials
python -m comicblock build    <project>                    # set + cast -> build/set.blend (+ build/plan.png)
python -m comicblock plot     <project> [CAM ...]          # empty-set renders per plot camera -> build/plot/
python -m comicblock stage    <project> <id ...|all> [--save]
python -m comicblock render   <project> <id> <file.blend>  # artist adjusted a staged scene by hand: render as is
python -m comicblock prompt   <project> <id ...>           # the exact prompt + references; spends nothing
python -m comicblock generate <project> <id ...> [--provider scenario|manual|dry] [--outputs N]
python -m comicblock import   <project> <id> <image ...>   # results made by hand in a web tool
python -m comicblock review   <project> <id ...|all> [--name NAME]
python -m comicblock fit      <project> <character> <body.obj> [--up y|z]   # optional MPFB body fit
```

## The loop: stage, check, generate, review

1. **Stage.** Write or adjust the panel's spec in `panels.py`, then `stage`.
2. **Check the blockout at full size.** Open `blockout/<id>.png` with the Read tool and look at it. Check:
   - the figures are distinct, and the hands that matter sit clear of the body silhouette
   - the feet are on the floor, nothing intersects, the heads point where the gaze should go
   - the props and set features the beat needs are in frame (see `blockout/<id>.json` "features")
   - the 180-degree line is kept: screen order matches the neighbouring panels

   Fix the spec and restage until it reads. Show the user the blockout and describe what you checked.
3. **Generate.** Run `prompt` first and read the prompt. Then **ask the user before any spending run**:
   name the panels, the provider and model, and the expected cost (about 25 CU a panel for 2 outputs on GPT
   Image 2.5 Sunburst; refusals still charge). Run one panel at a time or a small batch.
4. **Review at full size.** Open every output with Read, not just the contact sheet. Check:
   - likeness against the sheets
   - poses and facing against the blockout
   - left-right order
   - props, and nothing invented
   - hands and handedness

   Use `review` for the side-by-side sheet. Let the user pick.
5. **Restage rather than rerun.** If both outputs fail, find the cause in the blockout or the prompt first:
   - a head facing forward
   - a gesture hidden by the body
   - a long-lens crop
   - a feature named but not shown

   Almost every failed rerun in production traced back to the blockout. Rerun only after changing something.

## Rules that cost credits to learn

- **Stop at the first 429 and read it.** The CLI already stops. Show the user the message. It may be the plan's
  API cap, not an hourly rate limit, and retrying can lengthen the limit. Never retry in a loop, and never set up a
  retry loop yourself.
- **Refusals still charge.** Keep the mannequins flat grey with outline-only ink (the build does this). Don't
  name famous superhero costumes; describe them instead.
- **Gaze follows the HEAD, not the eyes.** Set `turn` (positive toward the character's own left) and `tilt`
  (positive tips the head down, negative lifts the chin) toward the target. `look` alone barely registers.
- **Keep gestures clear of the silhouette.** A hand in front of the torso vanishes.
- **Close-up insert of a held prop:** set `hide_cast=True`. Cast-free shots automatically send no sheets.
- **Framing:** for medium and close shots, move the camera closer (`dolly=True` from a plot camera, or an
  explicit `cam` nearer the cast), at about 35-50 mm. Don't crop with a long lens: the `max_lens` cap (50 mm)
  widens the frame instead. Wide establishing shots can use the plot camera with a fixed `lens`.
- **One axis per scene.** Keep every camera on one side of the line between the characters who face each other.
- **The prompt names only the set features in frame**, occlusion-tested. Every feature listed in project.yaml
  needs real geometry in `set.py`, or the model invents one. Missing set pieces get duplicated or invented, so
  build them.
- **Empty hands get props invented.** The prompt forbids it. If a character holds something, add a prop (`held`)
  and name it in the action.
- **Tone by prohibition.** Write what is visible (expression, gesture). Never explain the joke. If a look keeps
  coming out wrong, forbid the wrong thing ("no smirk").
- **The artist moved figures by hand?** Use `stage <id> --save`, let them adjust `build/staged/<id>.blend` in
  Blender and save, then `render <project> <id> <that .blend>`. Never restage over hand edits, and update the
  action text to match the new pose.

## Writing specs (see `comicblock/panels.py` and `comicblock/poses.py`)

- Poses are in the character's rest frame: the character faces -Y, their own left is +X, in metres. Start from
  `STAND`, `SIT` or `KNEEL_R` and override with `P(BASE, turn=30, tilt=10, ...)`. Set hands with
  `hands(left, right)`, or use the named sets (`ARMS_CROSSED`, `BEHIND_BACK`, `HANDS_ON_HIPS`, `CLASPED`,
  `ON_KNEES`, `SHRUG`).
- Pin hands to world points with `world_ik={"left_hand_ik": (x, y, z)}` (a door edge, a table, a shoulder).
- `left_grip` and `right_grip` curl the fingers in degrees: about 25 relaxed, 60-70 holding something.
- Floor marks (`at`) and facings (`face`) are world (x, y). Use `build/plan.png` to place them, and keep recurring
  marks as named constants at the top of `panels.py`, with a continuity note in its docstring.
- The `action` is one or two sentences: who does what, with what expression, using LEFT and RIGHT explicitly when
  handedness matters.
- After any change to `set.py`, characters or heights, run `build` again.

## Starting a new project

1. Copy `examples/starter` to `projects/<name>` (or anywhere), then delete its `build/`, `blockout/` and `gen/`.
2. Ask the user for:
   - each character's name, **true height**, a one-line look (costume and hair, as visible), and the sheet files
   - the style block
   - the location's plan (rough dimensions; where the doors, windows and main furniture are)
3. Write `project.yaml`, `set.py` (build it with `kit`: `shell`, `door`, `window`, `box`, `cyl`, `table`,
   `chair`, `shelves`, `chandelier`; see `comicblock/bl/kit.py`), the features with sample points, and 3-5
   plot cameras.
4. `doctor`, `build`, then `plot`. Show the user `build/plan.png` and the plot renders before staging anything.
5. Character sheets come from the user. If they have none yet, say plainly that results depend on them; the
   placeholders in the starter only prove the pipeline.

## Setup problems

- **MPFB missing:** in Blender, open Edit > Preferences > Get Extensions, search for MPFB, and install it. It is
  GPL and installed by the user, never bundled.
- **Blender not found:** set `blender:` in `project.yaml` or the `COMICBLOCK_BLENDER` environment variable.
- **Scenario credentials:** a CSV with columns `id,secret` at the `generation.credentials` path (outside the repo),
  or `SCENARIO_API_KEY` and `SCENARIO_API_SECRET`, plus `scenario_project` or `SCENARIO_PROJECT_ID`. Never read a
  key aloud, print it, or commit it.
- **No API at all:** use `--provider manual`. It writes `manual/<id>/` with the prompt and the numbered references
  for any web tool. Then run `import`.
