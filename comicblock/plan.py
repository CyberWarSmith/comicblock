"""Top-down floor plan of the built set with the camera plot and features -> build/plan.png (needs Pillow).

Reads build/plan.json, which `comicblock build` writes. Walls are filled, furniture outlined, fourth walls red,
cameras blue arrows, features green dots. Use it to place floor marks and check the 180-degree line.
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

SKIP = ("Floor", "Ceiling", "Beam", "Board", "Rug", "Runner", "Trans", "Mull", "Glass", "Tile", "Rib")


def _font(size):
    for name in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw(cfg, scale=90, pad=70):
    src = os.path.join(cfg["paths"]["build"], "plan.json")
    if not os.path.isfile(src):
        raise SystemExit("No build/plan.json: run `comicblock build` first.")
    with open(src, encoding="utf-8") as fh:
        P = json.load(fh)
    objs = [o for o in P["objects"] if o["z0"] < 2.6 and o["z1"] > 0.03 and not any(k in o["name"] for k in SKIP)]
    xs = [o["x0"] for o in P["objects"]] + [o["x1"] for o in P["objects"]]
    ys = [o["y0"] for o in P["objects"]] + [o["y1"] for o in P["objects"]]
    for c in P["cameras"].values():
        xs.append(c["pos"][0]); ys.append(c["pos"][1])
    X0, X1, Y0, Y1 = min(xs) - 0.5, max(xs) + 0.5, min(ys) - 0.8, max(ys) + 0.5
    W, H = int((X1 - X0) * scale) + 2 * pad, int((Y1 - Y0) * scale) + 2 * pad
    px = lambda x, y: (pad + (x - X0) * scale, pad + (Y1 - y) * scale)
    img = Image.new("RGB", (W, H), (245, 241, 232))
    d = ImageDraw.Draw(img)
    f, fs = _font(18), _font(13)
    for name, (x0, x1, y0, y1) in (P.get("rooms") or {}).items():
        a, b = px(x0, y1), px(x1, y0)
        d.rectangle([a, b], fill=(232, 224, 208), outline=(120, 110, 100))
        d.text(((a[0] + b[0]) / 2, a[1] + 14), name.upper(), fill=(90, 70, 60), font=f, anchor="mt")
    for o in sorted(objs, key=lambda o: o["z1"]):
        a, b = px(o["x0"], o["y1"]), px(o["x1"], o["y0"])
        if b[0] - a[0] < 1 or b[1] - a[1] < 1:
            continue
        if o["name"].startswith("4W_"):
            if "_" not in o["name"][3:]:
                d.rectangle([a, b], outline=(200, 60, 60), width=3)
                d.text((a[0], b[1] + 4), "fourth wall " + o["name"], fill=(200, 60, 60), font=fs)
            else:
                d.rectangle([a, b], outline=(220, 140, 140))
        elif "Wall" in o["name"] or "Chimney" in o["name"]:
            d.rectangle([a, b], fill=(60, 50, 45))
        else:
            d.rectangle([a, b], outline=(150, 110, 80))
    for name, pts in (P.get("features") or {}).items():
        x, y = pts[0][0], pts[0][1]
        q = px(x, y)
        d.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(40, 140, 70))
        d.text((q[0] + 6, q[1] - 6), name, fill=(30, 110, 50), font=fs)
    for name, c in P["cameras"].items():
        (x, y, _), (lx, ly, _) = c["pos"], c["look"]
        a = px(x, y)
        dx, dy = lx - x, ly - y
        n = math.hypot(dx, dy) or 1
        b = px(x + dx / n * 0.8, y + dy / n * 0.8)
        d.ellipse([a[0] - 6, a[1] - 6, a[0] + 6, a[1] + 6], fill=(40, 90, 180))
        d.line([a, b], fill=(40, 90, 180), width=3)
        d.text((a[0] + 8, a[1] + 6), "%s %smm" % (name, c.get("lens", "")), fill=(40, 90, 180), font=fs)
    for i in range(math.ceil(X0), math.floor(X1) + 1):         # 1 m ticks along the bottom
        d.line([px(i, Y0 + 0.3), px(i, Y0 + 0.15)], fill=(0, 0, 0))
        d.text(px(i, Y0 + 0.12), "%d m" % i, fill=(0, 0, 0), font=fs, anchor="mt")
    d.text((pad, 20), "%s - set plan (north up)" % cfg["name"], fill=(0, 0, 0), font=f)
    out = os.path.join(cfg["paths"]["build"], "plan.png")
    img.save(out)
    return out
