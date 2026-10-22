#!/usr/bin/env python3
"""Draw the sparkle favicons with Pillow (no browser needed).

  python3 scripts/favicons.py

Draws a four-pointed sparkle with a small one at its upper right (SPARKLES), in star white (--star in
site.css) on the night page (--paper). Each sparkle's four tips are joined by quadratic curves pulled
in towards its centre (PULL); sparkle() is that shape, for the SVG and for the PNG and ICO renders.
Icons of GLOW_FROM px and up get a faint glow; the tab sizes do not.
Writes assets/favicon/: favicon.svg, favicon.ico (16/32/48), favicon-96x96.png,
apple-touch-icon.png (180), web-app-manifest-192x192.png, web-app-manifest-512x512.png,
site.webmanifest; and a copy of favicon.ico at the repo root, for browsers that ask for /favicon.ico.
"""
import json, math, os, re, shutil
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets", "favicon")


def token(name):
    """A colour token from :root in assets/css/site.css, e.g. --paper."""
    with open(os.path.join(ROOT, "assets", "css", "site.css"), encoding="utf-8") as fh:
        m = re.search(name + r"\s*:\s*(#[0-9A-Fa-f]{6})\b", fh.read())
    if not m:
        raise SystemExit(f"no {name} colour in assets/css/site.css")
    return m.group(1)


NIGHT, WHITE = token("--paper"), token("--star")
GRID = 32       # SPARKLES are in pixels of the 32px icon, which is favicon.svg's viewBox
# (centre x, centre y, tip radius): the main sparkle, a little left of and below the middle, and the
# small one a third its size at its upper right. Centres on the middle of a pixel keep the 32px icon crisp.
SPARKLES = ((15.5, 16.5, 11), (25.5, 6.5, 4))
PULL = .25      # each side's control point is on a diagonal, PULL x the radius from the centre:
                # 0 would make needle-thin arms, .5 a straight-sided diamond
SS = 16         # supersampling for the PNGs
GLOW_FROM, GLOW, GLOW_R = 180, .25, .03   # icons this size and up: a blurred copy of the sparkles under
                                          # them, at GLOW opacity, blurred by GLOW_R x the size


def sparkle(x, y, r):
    """A sparkle centred on (x, y) with tips r away, as its four sides from the top tip clockwise:
    (start tip, control point, end tip) of each quadratic curve."""
    tips = [(x, y - r), (x + r, y), (x, y + r), (x - r, y)]
    ctrl = [(x + sx * PULL * r, y + sy * PULL * r) for sx, sy in ((1, -1), (1, 1), (-1, 1), (-1, -1))]
    return [(tips[i], ctrl[i], tips[(i + 1) % 4]) for i in range(4)]


def png(size):
    """The icon at size px: SPARKLES scaled to it, each centre moved to the middle of its pixel and each
    radius rounded to whole pixels, so the arms end in one crisp pixel at 16 and 32px; drawn SS times
    larger and averaged down."""
    k, S = size / GRID, size * SS
    mask = Image.new("L", (S, S), 0)
    draw = ImageDraw.Draw(mask)
    for x, y, r in SPARKLES:
        pts = []
        for (x0, y0), (qx, qy), (x1, y1) in sparkle(math.floor(x * k) + .5, math.floor(y * k) + .5, round(r * k)):
            for t in (i / 128 for i in range(128)):
                pts.append((((1 - t) ** 2 * x0 + 2 * (1 - t) * t * qx + t * t * x1) * SS,
                            ((1 - t) ** 2 * y0 + 2 * (1 - t) * t * qy + t * t * y1) * SS))
        draw.polygon(pts, fill=255)
    mask = mask.reduce(SS)
    im, white = Image.new("RGB", (size, size), NIGHT), Image.new("RGB", (size, size), WHITE)
    if size >= GLOW_FROM:
        glow = mask.filter(ImageFilter.GaussianBlur(GLOW_R * size)).point(lambda v: round(v * GLOW))
        im = Image.composite(white, im, glow)
    return Image.composite(white, im, mask)


def path(x, y, r):
    """sparkle(x, y, r) as SVG path data."""
    sides = sparkle(x, y, r)
    (x0, y0), _, _ = sides[0]
    return f"M{x0:g} {y0:g}" + "".join(f"Q{qx:g} {qy:g} {x1:g} {y1:g}" for _, (qx, qy), (x1, y1) in sides) + "Z"


def svg():
    """The sparkles in the 32px icon's coordinates, on a rounded square of night."""
    paths = "".join(f'<path fill="{WHITE}" d="{path(*s)}"/>' for s in SPARKLES)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}">'
            f'<rect width="{GRID}" height="{GRID}" rx="{GRID * .2:g}" fill="{NIGHT}"/>{paths}</svg>\n')


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "favicon.svg"), "w", encoding="utf-8") as fh:
        fh.write(svg())
    png(96).save(os.path.join(OUT, "favicon-96x96.png"), optimize=True)
    png(180).save(os.path.join(OUT, "apple-touch-icon.png"), optimize=True)
    png(192).save(os.path.join(OUT, "web-app-manifest-192x192.png"), optimize=True)
    png(512).save(os.path.join(OUT, "web-app-manifest-512x512.png"), optimize=True)
    small = [png(n) for n in (16, 32, 48)]  # drawn at each size, not scaled down from a large one
    small[-1].save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)], append_images=small[:-1])
    shutil.copyfile(os.path.join(OUT, "favicon.ico"), os.path.join(ROOT, "favicon.ico"))
    manifest = {"name": "Hanna Pálya", "short_name": "Hanna Pálya",
                "icons": [{"src": "/assets/favicon/web-app-manifest-192x192.png", "sizes": "192x192", "type": "image/png"},
                          {"src": "/assets/favicon/web-app-manifest-512x512.png", "sizes": "512x512", "type": "image/png"}],
                "theme_color": NIGHT, "background_color": NIGHT, "display": "browser"}
    with open(os.path.join(OUT, "site.webmanifest"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    print("favicons written to", OUT)


if __name__ == "__main__":
    main()
