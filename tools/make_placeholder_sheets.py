"""Draw the starter example's placeholder character sheets (front and side, flat colour blocks).

    python tools/make_placeholder_sheets.py

They exist so the example runs end to end. Replace them with real, approved character sheets: the sheets are the
only source of likeness and style the image model gets.
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "examples", "starter", "sheets")
CHARS = {
    "ada": dict(name="ADA", h=1.68, skin=(236, 200, 170), hair=(35, 28, 30), top=(214, 170, 60), shirt=(245, 245, 240),
                legs=(50, 50, 60), shoes=(110, 70, 40), bob=True, glasses=True, beard=False),
    "ben": dict(name="BEN", h=1.82, skin=(240, 205, 180), hair=(190, 80, 40), top=(70, 120, 70), shirt=(140, 140, 145),
                legs=(70, 90, 140), shoes=(230, 230, 230), bob=False, glasses=False, beard=True),
}


def font(n):
    for f in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, n)
        except OSError:
            pass
    return ImageFont.load_default()


def figure(d, cx, top, H, c, side=False):
    u = H / 8.0                                     # eight heads tall
    head_w = u * (0.62 if side else 0.7)
    d.ellipse([cx - head_w / 2, top, cx + head_w / 2, top + u], fill=c["skin"], outline=(0, 0, 0), width=3)
    if c["bob"]:
        d.pieslice([cx - head_w / 2 - 8, top - 8, cx + head_w / 2 + 8, top + u * 1.1], 180, 360, fill=c["hair"])
        d.rectangle([cx - head_w / 2 - 8, top + u * 0.45, cx - head_w / 2 + 6, top + u * 0.85], fill=c["hair"])
        if not side:
            d.rectangle([cx + head_w / 2 - 6, top + u * 0.45, cx + head_w / 2 + 8, top + u * 0.85], fill=c["hair"])
    else:
        for i in range(7):                          # curls
            x = cx - head_w / 2 + i * head_w / 6
            d.ellipse([x - 12, top - 14, x + 12, top + 10], fill=c["hair"])
    if c["beard"]:
        d.chord([cx - head_w / 2 + 4, top + u * 0.45, cx + head_w / 2 - 4, top + u * 1.08], 0, 180, fill=c["hair"])
    if c["glasses"] and not side:
        for s in (-1, 1):
            d.ellipse([cx + s * head_w * 0.22 - 11, top + u * 0.42 - 11, cx + s * head_w * 0.22 + 11, top + u * 0.42 + 11], outline=(0, 0, 0), width=3)
    sh = u * (1.0 if side else 2.0)                 # shoulder width
    neck = top + u
    d.polygon([(cx - sh / 2, neck + u * 0.2), (cx + sh / 2, neck + u * 0.2), (cx + sh * 0.42, neck + u * 2.9), (cx - sh * 0.42, neck + u * 2.9)],
              fill=c["top"], outline=(0, 0, 0))
    d.rectangle([cx - u * 0.18, neck + u * 0.2, cx + u * 0.18, neck + u * 1.6], fill=c["shirt"])
    for s in ((-1, 1) if not side else (0,)):
        ax = cx + s * sh / 2 if s else cx
        d.polygon([(ax - u * 0.18, neck + u * 0.25), (ax + u * 0.18, neck + u * 0.25), (ax + u * 0.14 + s * u * 0.15, neck + u * 3.0), (ax - u * 0.14 + s * u * 0.15, neck + u * 3.0)],
                  fill=c["top"], outline=(0, 0, 0))
        d.ellipse([ax + s * u * 0.15 - u * 0.14, neck + u * 2.95, ax + s * u * 0.15 + u * 0.14, neck + u * 3.3], fill=c["skin"], outline=(0, 0, 0))
    hip = neck + u * 2.9
    for s in ((-1, 1) if not side else (0,)):
        lx = cx + s * u * 0.32
        d.polygon([(lx - u * 0.3, hip), (lx + u * 0.3, hip), (lx + u * 0.18, top + H - u * 0.25), (lx - u * 0.18, top + H - u * 0.25)],
                  fill=c["legs"], outline=(0, 0, 0))
        d.rectangle([lx - u * 0.24, top + H - u * 0.28, lx + u * 0.24 + (u * 0.25 if side else 0), top + H], fill=c["shoes"], outline=(0, 0, 0))


def main():
    os.makedirs(OUT, exist_ok=True)
    for key, c in CHARS.items():
        W, Hh = 1536, 1024
        img = Image.new("RGB", (W, Hh), (238, 236, 230))
        d = ImageDraw.Draw(img)
        H = 820 * c["h"] / 1.85
        top = 940 - H
        figure(d, 470, top, H, c)
        figure(d, 1060, top, H, c, side=True)
        d.line([(80, 940), (W - 80, 940)], fill=(120, 120, 120), width=2)
        d.text((60, 30), "%s  -  %.2f m" % (c["name"], c["h"]), fill=(20, 20, 20), font=font(44))
        d.text((60, 90), "PLACEHOLDER SHEET - replace with your approved character sheet", fill=(190, 40, 40), font=font(26))
        d.text((420, 960), "FRONT", fill=(80, 80, 80), font=font(26))
        d.text((1020, 960), "SIDE", fill=(80, 80, 80), font=font(26))
        p = os.path.join(OUT, "%s_sheet.png" % key)
        img.save(p)
        print(p)


if __name__ == "__main__":
    main()
