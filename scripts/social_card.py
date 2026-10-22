#!/usr/bin/env python3
"""Render assets/img/social-card.png (1200x630), the image shown when the site is shared.

  python3 scripts/social_card.py

Lays out a night card (the sky, a few of the site's stars, the moonlit jellyfish on the right with
its faint halo, and the name and role in Quicksand, the site's one typeface) with the site's own
stylesheet (so the jellyfish has the site's moonlight colours), and
screenshots it with headless Chrome. The name and role are `title` and `tagline` in _config.yml
(the role line breaks after its first comma), so re-run this after changing either. Needs Google
Chrome; run scripts/build_illustrations.py and scripts/fetch_fonts.py first.
"""
import html, os, re, signal, subprocess, tempfile, time
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
OUT = os.path.join(ROOT, "assets", "img", "social-card.png")
ILL = os.path.join(ROOT, "_includes", "illustrations")
STARS = {"s1": (318, 64), "s2": (612, 520), "s5": (1146, 40), "s7": (96, 92), "s3": (690, 128), "s8": (1150, 560)}

CARD = """<!doctype html><html><head><meta charset="utf-8"><style>%(fonts)s
%(site)s
html, body { width: 1200px; height: 630px; overflow: hidden; }
body::before { display: none; }
.card {
  position: relative; width: 1200px; height: 630px; overflow: hidden;
  /* the moon halo sits behind the bell as on the page: sized and placed to the 560px jellyfish below */
  background: radial-gradient(622px 498px at 939px 130px, rgb(220 228 230 / .10), transparent 70%%) no-repeat,
              radial-gradient(44rem 30rem at 84%% 20%%, rgb(24 62 88 / .38), transparent 70%%) no-repeat,
              linear-gradient(180deg, var(--sky-top), var(--sky-mid) 60%%, var(--sky-low));
}
.card .star { position: absolute; width: 16px; height: 16px; overflow: visible; fill: none; stroke: var(--star);
              stroke-width: 1.1px; stroke-linecap: round; opacity: .85; }
%(star_pos)s
.text { position: absolute; left: 88px; top: 0; bottom: 0; width: 570px; display: flex; flex-direction: column; justify-content: center; }
.text h1 { font: 300 92px/1.05 var(--font); letter-spacing: -.005em; white-space: nowrap; }
.text p { margin: 0; font: 400 32px/1.35 var(--font); }
.text .role { margin-top: 30px; max-width: 520px; }
.text .site { margin-top: 18px; color: var(--muted); }
.card .jelly { position: absolute; right: -36px; top: 22px; width: 560px; }
</style></head><body><div class="card">
%(stars)s
<div class="text"><h1>%(name)s</h1>
<p class="role">%(role)s</p><p class="site">hannapalya.com</p></div>
<div class="jelly"><div class="float">%(jelly)s</div></div>
</div></body></html>"""


def png_complete(path):
    """True once the PNG at path ends with its IEND chunk (Chrome has finished writing it)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(-8, os.SEEK_END)
            return fh.read() == b"IEND\xaeB`\x82"
    except OSError:
        return False


def screenshot(page, shot, tmp, timeout=120):
    """Run headless Chrome on page. Chrome (seen with 154) writes the screenshot and then keeps
    running instead of exiting, so poll for a finished PNG and stop Chrome's process group."""
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--force-prefers-reduced-motion",
           "--allow-file-access-from-files", f"--user-data-dir={tmp}/prof", "--window-size=1200,630",
           "--virtual-time-budget=4000", f"--screenshot={shot}", "file://" + page]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + timeout
    try:
        while time.time() < deadline and not png_complete(shot) and proc.poll() is None:
            time.sleep(0.2)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # Chrome and its helper processes
        except (ProcessLookupError, PermissionError):  # already gone (macOS: EPERM when only zombies remain)
            pass
        proc.wait()
    if not png_complete(shot):
        raise RuntimeError("Chrome did not write a complete screenshot")


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def config(key):
    """A top-level one-line value in _config.yml, such as title or tagline."""
    m = re.search(rf"^{key}:[ \t]*(.+?)[ \t]*$", read(ROOT, "_config.yml"), re.M)
    if not m:
        raise SystemExit(f"no `{key}:` line in _config.yml")
    return m.group(1).strip("\"'")


def main():
    name, role = html.escape(config("title")), html.escape(config("tagline")).replace(", ", ",<br>", 1)
    fonts = read(ROOT, "assets", "css", "fonts.css")
    fonts = fonts.replace("url(/assets/fonts/", "url(file://" + os.path.join(ROOT, "assets", "fonts") + "/")
    sky = read(ILL, "sky.html")
    stars = "".join(re.search(rf'<svg class="star {k}".*?</svg>', sky).group(0) for k in STARS)
    star_pos = "".join(f".card .{k} {{ left: {x}px; top: {y}px; }}\n" for k, (x, y) in STARS.items())
    jelly = "".join(read(ILL, f"jelly-{k}.svg") for k in ("back", "bell", "arms", "front"))
    page_html = CARD % {"fonts": fonts, "site": read(ROOT, "assets", "css", "site.css"), "stars": stars,
                        "star_pos": star_pos, "jelly": jelly, "name": name, "role": role}
    with tempfile.TemporaryDirectory() as tmp:
        page = os.path.join(tmp, "card.html")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(page_html)
        shot = os.path.join(tmp, "card.png")
        screenshot(page, shot, tmp)
        im = Image.open(shot).convert("RGB").crop((0, 0, 1200, 630))
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        im.quantize(colors=256, method=Image.MEDIANCUT).save(OUT, optimize=True)
    print(f"{OUT}: {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main()
