"""Contact sheet: per panel, the blockout beside its outputs (and an optional draft/reference image).

A sheet is for an overview and for picking. Judge each output at FULL SIZE before accepting it: likeness, poses
against the blockout, left-right order, props, invented objects, hands.
A spec may set draft="path.png" (a rough or the original panel) to show it first in the row.
"""
import glob
import os

from PIL import Image, ImageDraw

from . import config
from . import panels as PN
from .plan import _font

ROW_H = 420


def _fit(im):
    im = im.convert("RGB")
    return im.resize((max(1, round(im.width * ROW_H / im.height)), ROW_H))


def sheet(cfg, ids, name=None):
    specs = PN.load(cfg["root"])
    ids = PN.select(specs, ids)
    rows = []
    for pid in ids:
        cells = []
        draft = specs[pid].get("draft")
        if draft and os.path.isfile(config.resolve(cfg, draft)):
            cells.append(("draft", Image.open(config.resolve(cfg, draft))))
        bo = os.path.join(cfg["paths"]["blockout"], "%s.png" % pid)
        if os.path.isfile(bo):
            cells.append(("blockout", Image.open(bo)))
        outs = sorted(glob.glob(os.path.join(cfg["paths"]["gen"], "%s_*.*" % glob.escape(pid))))
        outs = [o for o in outs if os.path.splitext(o)[1].lower() in (".png", ".jpg", ".jpeg", ".webp")
                and os.path.basename(o)[len(pid) + 1:].split(".")[0].isdigit()]
        cells += [("#" + os.path.basename(o)[len(pid) + 1:].split(".")[0], Image.open(o)) for o in outs]
        if cells:
            rows.append((pid, [(lbl, _fit(im)) for lbl, im in cells]))
    if not rows:
        raise SystemExit("Nothing to review yet for %s" % ", ".join(ids))
    W = max(sum(c.width + 12 for _, c in cs) for _, cs in rows) + 40
    img = Image.new("RGB", (W, len(rows) * (ROW_H + 60) + 10), "white")
    d = ImageDraw.Draw(img)
    f = _font(16)
    for i, (pid, cs) in enumerate(rows):
        y = 10 + i * (ROW_H + 60)
        d.text((10, y), "panel " + pid, fill=(200, 30, 30), font=f)
        x = 30
        for lbl, c in cs:
            d.text((x, y + 22), lbl, fill=(60, 60, 60), font=f)
            img.paste(c, (x, y + 44))
            x += c.width + 12
    os.makedirs(cfg["paths"]["review"], exist_ok=True)
    out = os.path.join(cfg["paths"]["review"], "%s.png" % (name or "review_" + "_".join(ids)[:60]))
    img.save(out)
    return out
