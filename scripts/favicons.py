#!/usr/bin/env python3
"""Draw the jellyfish-bell favicons with Pillow (no browser needed).

  python3 scripts/favicons.py

Draws the bell mark (_includes/illustrations/jelly-mark.svg, made by build_illustrations.py) in the
jellyfish's moon white (--jelly in site.css) on the night page (--paper), with heavier lines so it
holds up at 16px. Writes assets/favicon/: favicon.svg, favicon.ico (16/32/48), favicon-96x96.png,
apple-touch-icon.png (180), web-app-manifest-192x192.png, web-app-manifest-512x512.png,
site.webmanifest; and a copy of favicon.ico at the repo root, for browsers that ask for /favicon.ico.
"""
import json, os, re, shutil
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "assets", "favicon")
MARK = os.path.join(ROOT, "_includes", "illustrations", "jelly-mark.svg")


def token(name):
    """A colour token from :root in assets/css/site.css, e.g. --paper."""
    with open(os.path.join(ROOT, "assets", "css", "site.css"), encoding="utf-8") as fh:
        m = re.search(name + r"\s*:\s*(#[0-9A-Fa-f]{6})\b", fh.read())
    if not m:
        raise SystemExit(f"no {name} colour in assets/css/site.css")
    return m.group(1)


NIGHT, JELLY = token("--paper"), token("--jelly")
PAD = 0.12      # clear space around the mark, as a fraction of the icon
WIDTH = {1.0: 0.07, 0.75: 0.052, 0.6: 0.045}  # stroke width as a fraction of a 32px icon, by path opacity
NUM = re.compile(r"-?(?:\d+\.?\d*|\.\d+)")


def mark_paths():
    """The mark's paths as (opacity, points, closed), in its own 32-unit coordinates.
    medusa.py writes each as an absolute M, then relative l, optionally closed with z."""
    with open(MARK, encoding="utf-8") as fh:
        svg = fh.read()
    out = []
    for op, d in re.findall(r'<path(?: opacity="([\d.]+)")? d="([^"]+)"', svg):
        m = re.fullmatch(r"M([^lz]+)l([^z]+)(z?)", d)
        if not m:
            raise SystemExit(f"unexpected path data in {MARK}: {d[:40]}")
        x, y = map(float, NUM.findall(m.group(1)))
        rel = list(map(float, NUM.findall(m.group(2))))
        pts = [(x, y)]
        for dx, dy in zip(rel[::2], rel[1::2]):
            x, y = x + dx, y + dy
            pts.append((x, y))
        out.append((float(op or 1), pts, bool(m.group(3))))
    return out


def frame(paths):
    """A square box (x, y, side) around the mark, with PAD clear space on every side."""
    xs = [x for _, pts, _ in paths for x, _ in pts]
    ys = [y for _, pts, _ in paths for _, y in pts]
    side = max(max(xs) - min(xs), max(ys) - min(ys)) / (1 - 2 * PAD)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    return cx - side / 2, cy - side / 2, side


def mix(op):
    """The moon white at this opacity over the night (flattened, so overlapping lines do not darken)."""
    a, b = (tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in (NIGHT, JELLY))
    return tuple(round(p + (q - p) * op) for p, q in zip(a, b))


def png(size, ss=4):
    """The icon at size px: lines are heavier, relative to the icon, the smaller it is."""
    paths = mark_paths()
    heft = (32 / size) ** .4
    x0, y0, side = frame(paths)
    S = size * ss
    k = S / side
    im = Image.new("RGB", (S, S), NIGHT)
    dr = ImageDraw.Draw(im)
    for op, pts, closed in sorted(paths, key=lambda p: p[0]):  # faint lines first, the outline on top
        xy = [((x - x0) * k, (y - y0) * k) for x, y in pts + (pts[:1] if closed else [])]
        w = max(1, round(WIDTH[op] * heft * S))
        dr.line(xy, fill=mix(op), width=w, joint="curve")
        for px, py in (xy[0], xy[-1]):  # round caps
            dr.ellipse((px - w / 2, py - w / 2, px + w / 2, py + w / 2), fill=mix(op))
    return im.resize((size, size), Image.LANCZOS)


def svg():
    x0, y0, side = frame(mark_paths())
    with open(MARK, encoding="utf-8") as fh:
        ds = re.findall(r'<path(?: opacity="([\d.]+)")? d="([^"]+)"', fh.read())
    lines = []
    for op, d in ds:
        attr = f' opacity="{op}"' if op else ""
        lines.append(f'<path{attr} stroke-width="{WIDTH[float(op or 1)] * side:.2f}" d="{d}"/>')
    lines = "".join(lines)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.2f} {y0:.2f} {side:.2f} {side:.2f}">'
            f'<rect x="{x0:.2f}" y="{y0:.2f}" width="{side:.2f}" height="{side:.2f}" rx="{side * .2:.2f}" fill="{NIGHT}"/>'
            f'<g fill="none" stroke="{JELLY}" stroke-linecap="round" stroke-linejoin="round">{lines}</g></svg>\n')


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
