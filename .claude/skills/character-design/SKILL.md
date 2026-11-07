---
name: character-design
description: Guided Q&A that takes a newcomer from an idea for a character to approved character sheets for comicblock. Use when the user wants to create, design or redesign a character, has no character sheets yet, asks how to make sheets or a turnaround or an expression sheet, or is starting a comic and doesn't know where to begin with the cast.
---

# Character design: from an idea to approved sheets

The character sheets are the **only** source of likeness and style the image model gets for every panel. Time spent
here saves credits everywhere else. Your job is to interview the user, one small step at a time, turn the answers into
a precise visual brief, make the sheets, and help them judge the results.

The user is likely new to this. Ask **one or two questions at a time**, in plain words, and give examples. Use
AskUserQuestion when there are clear options (build, age range, style). Use open questions for the personal parts.
Never dump the whole questionnaire at once. Summarise what you have so far every few answers so they can correct you.

## Step 0: the project style (once per project)

If `project.yaml` has no real `style:` yet, settle it first, because every character must share it:

- What should the comic look like? Offer example directions: "clean cel animation", "inky noir",
  "watercolour storybook", "manga screentone", "European bande dessinée". Ask for a comic or show they love, then
  describe it in **visual terms only** (line, shading, palette, lighting). Never put an artist's or studio's name
  in the prompt.
- Write it as the `style:` block: one or two sentences.

## Step 1: who they are (2-3 questions)

- Their name, and their role in the story, in one sentence.
- Their personality in three words. This shapes the expressions and acting, not the costume.
- Is there an existing sketch, photo of an outfit, or reference? If so, ask for the file path and keep it for
  `--ref`.

## Step 2: body (this sets the mannequin, so be exact)

- **True height**, in centimetres or feet and inches. Convert to metres. Heights must be consistent across the
  cast: ask how they compare to the others ("a head taller than Ada").
- **Build**, in silhouette words: slight, average, stocky, lanky, broad-shouldered, curvy, heavy-set, muscular.
- **Age range.**

Map these to MPFB macros in `project.yaml` under `mpfb: macros:`. All values are 0-1; start here and adjust by eye
against the guide:

| Answer | Macro |
| --- | --- |
| female / male / in between | `gender` 0.0 / 1.0 / 0.5 |
| age 15 / 25 / 30s / 40s / 60s / 80s | `age` about 0.28 / 0.50 / 0.54 / 0.62 / 0.77 / 0.92 (MPFB: 0.5 = 25 years, 1.0 = 90) |
| slight / average / heavy | `weight` 0.3 / 0.5 / 0.75 |
| soft / average / athletic / very muscular | `muscle` 0.3 / 0.5 / 0.7 / 0.9 |
| curvy figure | `cupsize` 0.7-1.0, plus wider hips (a design note) |

## Step 3: what we see

Walk through these one at a time. Push for **specific, visible** details: "short dark bob with a blunt fringe",
not "nice hair".

- **Face:** shape, eyes, brows, glasses, facial hair, marks (freckles, scar).
- **Hair:** length, shape, colour.
- **Costume, layer by layer:** top, outer layer, bottoms, shoes, and the one signature item.
- **Palette:** 3-5 colours.
- **Tells:** at least one **asymmetric** detail (a watch on the LEFT wrist, a bag strap from the RIGHT shoulder, a
  scar over one eye). Panels use these to keep left and right straight.
- **Avoid:** things the model keeps adding, or that the character must never have (no hat, no jewellery).

**Wording rules** (each one cost credits to learn):

- Describe what should be there, not a genre label. "Vampire" adds pointed ears and grey skin; "witch" adds a hat.
  If the user wants a genre, translate it into the specific visible features they actually mean.
- Don't name famous characters or their costumes (refused, and still charged). Describe the costume instead.
- No nudity or underwear-only designs for sheets that panels will use.

## Step 4: write it down

1. Add or update the character in `project.yaml`:
   - `name`, `height`, `mpfb: macros:`
   - a `design:` block with role, age, build, face, hair, costume, palette, tells, avoid (format: top of
     `comicblock/sheets.py`)
   - a **one-line `look:`**: the visible essentials the panels repeat ("the tall man with curly red hair and a
     short beard, in a green raincoat over a grey jumper, jeans and white trainers")
   - `sheets: []` until approved
2. Write `characters/<key>/brief.md` for the user: the answers in prose, plus anything that didn't fit the fields
   (personality, story notes, open questions).
3. Read the summary back to the user and get a yes before spending anything.

## Step 5: the proportion guide

Run `python -m comicblock build <project>`, then `python -m comicblock sheet <project> <key> --dry`. This renders
`build/guides/<key>_guide.png`: the character's own mannequin, front and side, at true height. Show it to the
user with Read. Ask: "Is this the right height and build next to the others?" Adjust `height` and the `mpfb` macros
and rebuild until they say yes. The panels use this exact body, so getting it right here matters.

The `--dry` output also shows the exact prompt. Read it through for anything vague or genre-loaded.

## Step 6: generate drafts

- **Ask before spending.** Say the provider, the model and the cost: about 25 CU for two drafts on GPT Image 2.5
  Sunburst via Scenario. Refusals still charge.
- With no API, use `--provider manual`. It writes `manual/<key>_turnaround/` with the prompt and the guide to use in
  any web tool. Then run `python -m comicblock sheet-import <project> <key> turnaround <files>`.
- `python -m comicblock sheet <project> <key> [--ref sketch.png]` writes drafts to `sheets/drafts/`.
- Stop at the first 429 and show the user the message. Never retry in a loop.

## Step 7: judge the drafts at full size

Open every draft with Read and go through this checklist with the user:

- **Proportions** match the guide: head size, leg length, shoulder width.
- **Front and side** are the same person, in the same costume, at the same scale.
- Every brief item is there, with nothing extra (hats, jewellery, props, text, signatures, watermarks).
- The tells are on the **correct side**.
- The **style** is right. If a style is wrong now, it will be wrong in every panel.

If neither draft works, **change the brief, not the dice**: find what in the prompt caused the miss, fix the
wording, and only then generate again. Small fixes (a wrong colour, a stray mark, a signature) are cheaper to
paint over in an image editor than to regenerate.

## Step 8: clean up and lock

1. The user cleans the pick in their editor: paints out signatures, stray marks, anything unintended.
2. Save it as `sheets/<key>_turnaround.png` and add it to the character's `sheets:` in `project.yaml`.
3. Optionally, make an expression sheet: `python -m comicblock sheet <project> <key> --kind expressions`. It uses
   the approved turnaround as its reference. Judge it the same way, then add `sheets/<key>_expressions.png` as the
   second sheet.
4. Tell the user the character is **locked**. Changing the sheets later changes the character in every future
   panel, so redesigns are a deliberate step, not a tweak.
5. Hand over to the `comicblock` skill for sets and panels.
