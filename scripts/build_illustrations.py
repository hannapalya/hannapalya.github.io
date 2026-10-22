#!/usr/bin/env python3
"""Regenerate the site's illustrations into _includes/illustrations/.

  python3 scripts/build_illustrations.py

The night sky art of the home page, made with the same seeds and numbers as the original
drawing, so re-running it gives the same files:

  jelly-{back,bell,arms,front}.svg  the moon jellyfish from scripts/medusa.py, in four layers. The
                                    bell layer holds the gonads in their own group, so CSS can
                                    colour them (pearl white) and give them their own glow.
  sky.html                          hand-drawn stars: 6-ray asterisks and dot-crosses.
  illustrations.css                 the speck and grain tiles, as data URIs.

The jellyfish's stroke widths (medusa.py's layers.css) live in assets/css/site.css, ahead of the
night colours that override them; this script fails if the two have drifted apart. Every
generator here is deterministic, so re-running gives identical files.
"""
import math, os, random, re, shutil, subprocess, sys, tempfile
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "_includes", "illustrations")
SITE_CSS = os.path.join(ROOT, "assets", "css", "site.css")
JV = "-23 16 603 589"  # the jellyfish's viewBox (medusa.py's drawing bounds plus a margin)


def f(v, d=1):
    s = f"{v:.{d}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ----------------------------------------------------------------------------- the jellyfish
def run_medusa():
    """Run medusa.py in a temp dir; return its layer SVGs and layers.css."""
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(os.path.join(HERE, "medusa.py"), tmp)
        subprocess.run([sys.executable, os.path.join(tmp, "medusa.py")], cwd=tmp, check=True,
                       stdout=subprocess.DEVNULL)

        def read(name):
            with open(os.path.join(tmp, name), encoding="utf-8") as fh:
                return fh.read().strip()
        layers = {k: read(f"layer-{k}.svg") for k in ("back", "bell", "arms", "front")}
        return layers, read("layers.css")


def jelly_layer(svg):
    if f'viewBox="{JV}"' not in svg:
        raise SystemExit(f"medusa.py's viewBox is no longer {JV}; the trails' rim points assume it")
    return re.sub(r"^<svg[^>]*>|</svg>$", "", svg)


def jsvg(cls, inner):
    return (f'<svg class="jl {cls}" viewBox="{JV}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" '
            f'focusable="false">{inner}</svg>')


def build_jelly(layers):
    bell = jelly_layer(layers["bell"])
    gon = "".join(re.findall(r'<path class="j-(?:gonad|dots)"[^>]*/>', bell))
    bell = re.sub(r'<path class="j-(?:gonad|dots)"[^>]*/>', "", bell)
    assert gon.count("<path") == 2, "expected the gonads and their dots as two paths"
    return {
        "jelly-back.svg": jsvg("jl-back", jelly_layer(layers["back"])),
        "jelly-bell.svg": jsvg("jl-bell", f'<g class="bell breath">{bell}</g>'
                                         f'<g class="gonads">{gon}</g>'),
        "jelly-arms.svg": jsvg("jl-arms", jelly_layer(layers["arms"])),
        "jelly-front.svg": jsvg("jl-front", jelly_layer(layers["front"])),
    }


def check_layer_css(layers_css):
    """medusa.py's per-class stroke widths must be in site.css as written (they are kept there, not
    emitted here: inlined after site.css they would override its night colours)."""
    with open(SITE_CSS, encoding="utf-8") as fh:
        css = fh.read()
    rules = [ln for ln in layers_css.splitlines() if ln.strip()]
    stale = [ln for ln in rules if ln not in css]
    if stale:
        raise SystemExit("assets/css/site.css is missing medusa.py's jellyfish rules:\n  " + "\n  ".join(stale))


# ----------------------------------------------------------------------------- hand-drawn stars
# 6-ray asterisks of three unequal, slightly curved strokes, 7-11px across; some are a dot with a
# short cross
def asterisk(r, cx, cy, size):
    out, base = [], r.uniform(0, 60)
    for k in range(3):
        a = math.radians(base + k * 60 + r.uniform(-10, 10))
        L = size * r.uniform(.68, 1.0) / 2
        ox, oy = r.uniform(-.07, .07) * L, r.uniform(-.07, .07) * L
        bend = L * r.uniform(-.16, .16)
        ca, sa = math.cos(a), math.sin(a)
        x0, y0 = cx + ox - ca * L, cy + oy - sa * L
        x1, y1 = cx + ox + ca * L * r.uniform(.8, 1), cy + oy + sa * L * r.uniform(.8, 1)
        qx, qy = cx + ox - sa * bend, cy + oy + ca * bend
        out.append(f"M{f(x0, 2)} {f(y0, 2)}Q{f(qx, 2)} {f(qy, 2)} {f(x1, 2)} {f(y1, 2)}")
    return "".join(out)


def dotcross(r, cx, cy, size):
    h, v = size * .5, size * .42
    t = r.uniform(-.12, .12)
    return (f"M{f(cx - h, 2)} {f(cy + t * h, 2)}L{f(cx + h, 2)} {f(cy - t * h, 2)}"
            f"M{f(cx + t * v, 2)} {f(cy - v, 2)}L{f(cx - t * v, 2)} {f(cy + v, 2)}"), f"M{f(cx, 2)} {f(cy, 2)}h0"


def build_sky():
    srng = random.Random(8128)
    cross = {3, 7, 10}
    stars = []
    names = [f"s{i}" for i in range(1, 9)] + [f"m{i}" for i in range(1, 5)]  # s: desktop, m: phone
    for i, name in enumerate(names):
        size = srng.uniform(7.5, 10.5)
        if i in cross:
            a, b = dotcross(srng, 7, 7, size * .8)
            d = f'<path d="{a}"/><path class="star-dot" d="{b}"/>'
        else:
            d = f'<path d="{asterisk(srng, 7, 7, size)}"/>'
        stars.append(f'<svg class="star {name}" viewBox="0 0 14 14" focusable="false">{d}</svg>')
    return '<div class="sky" aria-hidden="true">' + "".join(stars) + "</div>"


# ----------------------------------------------------------------------------- textures
def uri(svg):
    return '"data:image/svg+xml,' + quote(svg, safe=" ='/:,.-") + '"'


def build_textures():
    krng = random.Random(512)
    tones = [("#7A7F84", .45, 1.0, 52), ("#A7ABAD", .55, 1.2, 26), ("#D9D6CE", .7, 1.5, 14), ("#FFFAF0", .9, 1.8, 8)]
    groups = []
    for col, op, w, nn in tones:
        d = "".join(f"M{krng.randrange(2, 510)} {krng.randrange(2, 510)}h0" for _ in range(nn))
        groups.append(f"<path stroke='{col}' stroke-opacity='{op}' stroke-width='{w}' d='{d}'/>")
    specks = ("<svg xmlns='http://www.w3.org/2000/svg' width='512' height='512' fill='none' stroke-linecap='round'>"
              + "".join(groups) + "</svg>")
    grain = ("<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'><filter id='n'>"
             "<feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/>"
             "<feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 1 0 0 0 0'/></filter>"
             "<rect width='180' height='180' filter='url(#n)'/></svg>")
    # site.css sizes and places both tiles; only the images come from here
    return (f"body::before{{background-image:url({uri(grain)})}}\n"
            f".sky::before{{background-image:url({uri(specks)})}}\n")


def main():
    layers, layers_css = run_medusa()
    check_layer_css(layers_css)
    files = build_jelly(layers)
    files["sky.html"] = build_sky()
    files["illustrations.css"] = build_textures()
    os.makedirs(OUT, exist_ok=True)
    for name, body in files.items():
        if "{{" in body or "{%" in body:
            raise SystemExit(f"{name} contains Liquid delimiters; Jekyll would try to render them")
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"{name}: {len(body.encode()) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
