"""Character sheets: from a design brief to approved sheets (the character-design skill drives this).

    python -m comicblock sheet <project> <key> [--kind turnaround|expressions] [--dry] [--provider P] [--ref F ...]
    python -m comicblock sheet-import <project> <key> <kind> <image ...>

turnaround: the first reference is a PROPORTION GUIDE, the character's own mannequin (true height and build)
rendered front and side by Blender, so the sheet is drawn over the proportions the panels will use. The method's
split holds here too: Blender decides structure, the image model decides appearance.
expressions: the first reference is the character's approved turnaround (their first sheet in project.yaml).

The design brief lives in project.yaml under the character:

    design:
      role: the landlord's no-nonsense niece          # who they are (shapes the acting, not the costume)
      age: late twenties
      build: slim, narrow shoulders, long legs        # silhouette words
      face: round face, freckles, thick straight brows
      hair: short dark bob with a blunt fringe
      costume: mustard cardigan over a white shirt, dark trousers, brown boots
      palette: mustard, white, charcoal, tan
      tells: a red watch on her LEFT wrist            # asymmetric details that show left from right in panels
      avoid: no hat, no jewellery                     # things the model tends to add

Drafts go to sheets/drafts/<key>_<kind>_<k>.png. The artist picks one, cleans it up (paint out signatures and
anything unintended), and it becomes sheets/<key>_<kind>.png, listed under the character's `sheets:`.
"""
import datetime
import json
import os
import shutil

from PIL import Image

from . import blender, config, providers

KINDS = ("turnaround", "expressions")
FIELDS = ("age", "build", "face", "hair", "costume", "palette", "tells")


def design_text(ch):
    d = ch.get("design") or {}
    parts = []
    for k in FIELDS:
        if d.get(k):
            parts.append("%s: %s" % ({"tells": "distinguishing details"}.get(k, k).capitalize(), str(d[k]).strip()))
    if not parts and ch.get("look"):
        parts.append("Look: " + ch["look"].strip())
    return ". ".join(parts) + ("." if parts else "")


def drafts_dir(cfg):
    return os.path.join(cfg["root"], "sheets", "drafts")


def make_guide(cfg, key, live=False):
    """Render the mannequin front and side and join them into build/guides/<key>_guide.png (1536 x 1024)."""
    res = blender.run(cfg, "guide", [key], blend=blender.set_blend(cfg), live=live)
    front, side = (Image.open(f).convert("RGB") for f in res["files"])
    out = Image.new("RGB", (1536, 1024), front.getpixel((5, 5)))
    out.paste(front, (0, 0))
    out.paste(side, (768, 0))
    path = os.path.join(cfg["paths"]["build"], "guides", "%s_guide.png" % key)
    out.save(path)
    return path, res["height"]


def build_request(cfg, key, kind, guide=None, refs=(), outputs=None):
    ch = cfg["characters"][key]
    name = ch["name"]
    d = ch.get("design") or {}
    style = (cfg.get("style") or "").strip()
    avoid = (" Avoid: " + str(d["avoid"]).strip().rstrip(".") + ".") if d.get("avoid") else ""
    ref_list, extra = [], ""
    if kind == "turnaround":
        if guide:
            ref_list.append(("guide", guide))
            intro = ("The first image is a proportion guide: a plain grey mannequin of this character, front view on the "
                     "left and side view on the right, at their true height and build. Draw a character model sheet "
                     "of %s over exactly these proportions: full body, front view on the left and side view on the "
                     "right, standing straight with arms relaxed at the sides, both views the same size, feet on one "
                     "ground line. The mannequin only sets the proportions: draw the character fully dressed in their "
                     "costume. " % name)
        else:
            intro = ("Draw a character model sheet of %s: full body, front view on the left and side view on the right, "
                     "standing straight with arms relaxed at the sides, both views the same size, feet on one ground "
                     "line. " % name)
        tail = (" Plain light flat background. Only this one character, shown twice. No props, no text, no labels, "
                "no signature, no watermark.")
    elif kind == "expressions":
        if not ch["sheets"]:
            raise SystemExit("%s has no approved sheet yet: make and approve a turnaround first." % name)
        first = ch["sheets"][0]
        ref_list.append(("turnaround", first if str(first).startswith("asset_") else config.resolve(cfg, first)))
        intro = ("The first image is the approved model sheet of %s. Draw an expression sheet of the same character: "
                 "six head-and-shoulders views in two rows of three - neutral, happy, angry, surprised, worried, "
                 "thinking - matching the face, hair, costume and drawing style of the model sheet exactly. " % name)
        tail = " Plain light flat background. No text, no labels, no signature, no watermark."
    else:
        raise SystemExit("kind must be one of %s" % ", ".join(KINDS))
    for i, r in enumerate(refs, 1):
        if not os.path.isfile(r):
            raise SystemExit("No such reference: %s" % r)
        ref_list.append(("artist_ref%d" % i, os.path.abspath(r)))
    if refs:
        extra = ("The %s attached image%s %s the artist's own sketches or references for this design: follow them for "
                 "the look. " % ("other" if ref_list[0][0] != "artist_ref1" else "", "s" if len(refs) > 1 else "",
                                 "are" if len(refs) > 1 else "is"))
    prompt = intro + extra + design_text(ch) + avoid + " " + style + tail
    return dict(prompt=" ".join(prompt.split()), refs=ref_list, width=1536, height=1024,
                outputs=int(outputs or cfg["generation"]["outputs"]), features=[],
                import_cmd="python -m comicblock sheet-import <project> %s %s <file> [<file> ...]" % (key, kind))


def _log(cfg, pid, entry):
    d = drafts_dir(cfg)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "sheets.json")
    log = json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {}
    log.setdefault(pid, []).append(entry)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(log, fh, indent=2)


def run(cfg, key, kind="turnaround", provider=None, outputs=None, refs=(), use_guide=True, live=False):
    if key not in cfg["characters"]:
        raise SystemExit("No character %r in project.yaml (add it with at least name, height and design first)" % key)
    guide = None
    if kind == "turnaround" and use_guide:
        guide, h = make_guide(cfg, key, live=live)
        print("proportion guide (%.2f m): %s" % (h, guide))
    req = build_request(cfg, key, kind, guide, refs, outputs)
    prov = providers.get(provider or cfg["generation"]["provider"], cfg)
    pid = "%s_%s" % (key, kind)
    try:
        res = prov.generate(pid, req, drafts_dir(cfg))
    except providers.RateLimited as e:
        print("\nRATE LIMITED (429) - stopping. The service said:\n%s\nRead it before trying again; never retry in a loop." % e)
        return 3
    if prov.name == "dry":
        return 0
    _log(cfg, pid, dict(time=datetime.datetime.now().isoformat(timespec="seconds"), provider=prov.name,
                        model=cfg["generation"]["model"], status=res.status, cost=res.cost, job=res.job,
                        outputs=[os.path.basename(f) for f in res.files], prompt=req["prompt"],
                        refs=[label for label, _ in req["refs"]]))
    print("%s %s%s %s" % (pid, res.status, (" %s CU" % res.cost) if res.cost is not None else "",
                          ", ".join(res.files)))
    if res.files:
        print("Look at each draft at full size. Pick one, clean it up, save it as sheets/%s_%s.png and list it under "
              "%s's sheets in project.yaml." % (key, kind, key))
    return 0


def import_drafts(cfg, key, kind, images):
    d = drafts_dir(cfg)
    os.makedirs(d, exist_ok=True)
    out = []
    for k, src in enumerate(images, 1):
        if not os.path.isfile(src):
            raise SystemExit("No such file: %s" % src)
        dst = os.path.join(d, "%s_%s_%d%s" % (key, kind, k, os.path.splitext(src)[1].lower() or ".png"))
        shutil.copyfile(src, dst)
        out.append(dst)
    _log(cfg, "%s_%s" % (key, kind), dict(time=datetime.datetime.now().isoformat(timespec="seconds"),
                                          provider="manual", status="imported", outputs=[os.path.basename(f) for f in out]))
    print("imported", ", ".join(out))
