"""Build the generation request for a panel: the prompt text and the ordered reference images. Pure Python.

Order of references: the blockout FIRST, then any extra references the spec names, then the sheets of each
character in shot (in cast order). A cast-free shot (no cast, or hide_cast) sends no sheets: sheets sent with an
empty insert make the model add people.

Prompt order, as proven in production:
  1. redraw the blockout keeping camera, framing, perspective, layout, positions, scale, poses and facing exactly,
     replacing each mannequin with the character from the sheets
  2. the action (one or two sentences: who does what, with what expression)
  3. the setting, plus ONLY the set features in frame (from blockout/<id>.json, occlusion-tested)
  4. the KEEP rule: add no doors, openings or props; hands hold nothing unless shown or named
  5. each character's look in one line
  6. the style block; the person count; no text
Carry tone by prohibition (no smirking, no winks); never describe the joke.
"""
import json
import os

from . import config

INTRO_CAST = ("The first image is a 3D staging blockout of this comic panel: grey mannequins and simple prop proxies "
              "in a model of the set. Redraw it as a finished comic panel, keeping its camera, framing, perspective, "
              "room layout and every figure's position, scale, pose and facing exactly as in the blockout. Replace "
              "each mannequin with the character, matching faces, hair and costumes exactly to the attached "
              "character sheets, with clear, expressive acting. ")
INTRO_EMPTY = ("The first image is a 3D staging blockout of this comic panel: simple prop proxies in a model of the "
               "set. Redraw it as a finished comic panel, keeping its camera, framing, perspective and layout exactly "
               "as in the blockout. ")
KEEP = ("Draw only the background features the blockout shows, where it shows them; do not add doors, doorways, "
        "windows, stairs, openings or furniture that are not in the blockout. Hands hold nothing unless the blockout "
        "shows a prop in them or the text names one; add no bags, cases or other objects. ")
COUNT = {0: "No people", 1: "One person only", 2: "Two people only", 3: "Three people only", 4: "Four people only",
         5: "Five people only", 6: "Six people only"}


def blockout_meta(cfg, pid):
    path = os.path.join(cfg["paths"]["blockout"], "%s.json" % pid)
    if not os.path.isfile(path):
        raise SystemExit("Panel %s has no blockout yet: run `comicblock stage <project> %s` first." % (pid, pid))
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build(cfg, pid, spec):
    """-> dict(prompt, refs=[(label, path or asset id)], width, height, outputs, features)."""
    meta = blockout_meta(cfg, pid)
    cast = [] if spec.get("hide_cast") else list(spec.get("cast", {}))
    feats = cfg["set"]["features"]
    seen = [feats[f]["text"] for f in meta["features"] if f in feats and feats[f].get("text")]
    setting = (cfg.get("setting") or "").strip()
    room = (setting + " " if setting else "") + ("In view: " + "; ".join(seen) + ". " if seen else "")
    extra = spec.get("refs", [])
    extra_text = "".join(r.get("text", "").strip() + " " for r in extra)
    action = spec.get("action", "").strip()
    style = (cfg.get("style") or "").strip()
    if cast:
        who = " ".join("%s is %s." % (cfg["characters"][k]["name"], cfg["characters"][k]["look"].strip())
                       for k in cast if cfg["characters"][k].get("look"))
        prompt = (INTRO_CAST + extra_text + action + " " + room + KEEP + who + " " + style + " " +
                  COUNT.get(len(cast), "%d people only" % len(cast)) + ". No text, no lettering, no speech balloons.")
    else:
        prompt = (INTRO_EMPTY + extra_text + action + " " + room + KEEP + style +
                  " No people. No text, no lettering, no speech balloons.")
    refs = [("blockout", meta["file"])]
    for i, r in enumerate(extra):
        refs.append(("ref%d" % (i + 1), config.resolve(cfg, r["file"]) if not str(r["file"]).startswith("asset_") else r["file"]))
    for k in cast:
        for j, s in enumerate(cfg["characters"][k]["sheets"]):
            refs.append(("%s_sheet%d" % (k, j + 1), s if str(s).startswith("asset_") else config.resolve(cfg, s)))
    w, h = spec.get("size", meta.get("size") or cfg["render"]["default_size"])
    return dict(prompt=" ".join(prompt.split()), refs=refs, width=int(w), height=int(h),
                outputs=int(spec.get("outputs", cfg["generation"]["outputs"])), features=meta["features"])
