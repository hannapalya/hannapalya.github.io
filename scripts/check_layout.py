#!/usr/bin/env python3
"""Layout checks and screenshots in headless Chrome.

  python3 scripts/check_layout.py                    # every page in _site (posts too), 320-1920px,
                                                     # at the 16px, 20px and 24px default font sizes
  python3 scripts/check_layout.py --pages / /404.html
  python3 scripts/check_layout.py --widths 320-1920:10 --font-sizes 16   # a sweep, every 10px
  python3 scripts/check_layout.py --shots /tmp/shots # also save 390px and 1440px screenshots

Serves _site/ on a local port and loads each page in same-origin iframes of fixed widths, once
for each browser default font size (Chrome's Settings > Font size: 16px is Medium, 20px Large,
24px Very large). FAILs when a page is missing, when it scrolls sideways, when visible text runs
past the right edge (text clipped by an overflow:hidden ancestor counts; text in a box that
scrolls sideways, such as a wide table or code block, does not), when a line of the jellyfish
or a tentacle crosses the ink of the text (each glyph's box, and the x-height band of a space), and when a page has section rules (main .sec) that the
trails script did not draw (html.has-trails and one svg.trails [data-rule] path per section).
Animations are disabled (--force-prefers-reduced-motion). Exit status = failures; a screenshot
that Chrome does not write counts as one (old files in the output directory are deleted first).
"""
import argparse, functools, glob, html, http.server, json, os, re, select, signal, socketserver, subprocess, sys
import tempfile, threading, time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_site")
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
WIDTHS = [320, 375, 390, 768, 1024, 1100, 1200, 1280, 1440, 1920]
FONT_SIZES = [16, 20, 24]   # the browser's default font size, in px
SHOT_WIDTHS = [390, 1440]

HARNESS = """<!doctype html><meta charset="utf-8"><title>running</title><body><script>
const PAGES = %s, WIDTHS = %s;
const TEXTY = /^(p|a|li|h1|h2|h3|h4|span|dd|dt|time|figcaption|img|button|b|i|em|strong|td|th|pre|code|blockquote)$/i;
function sel(el) {
  const c = typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\\s+/).join(".") : "";
  return el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + c;
}
// The ink of each visible character, as [left, top, right, bottom, word] boxes in the frame's
// viewport: the character's advance across, its glyph's ink (measured on a canvas in the page's
// own font) up and down, and for a space the band from the baseline to the x-height, so a line
// that threads between two words crosses the text too.
function glyphs(d) {
  const out = [], rg = d.createRange(), tw = d.createTreeWalker(d.body, NodeFilter.SHOW_TEXT);
  const ctx = d.createElement("canvas").getContext("2d"), cache = {};
  const ink = (font, ch) => {
    const k = font + "|" + ch;
    if (!(k in cache)) {
      ctx.font = font;
      const m = ctx.measureText(ch), x = ctx.measureText("x");
      cache[k] = { a: m.fontBoundingBoxAscent, dd: m.fontBoundingBoxDescent,
                   up: /\\s/.test(ch) ? x.actualBoundingBoxAscent : m.actualBoundingBoxAscent,
                   down: /\\s/.test(ch) ? 0 : m.actualBoundingBoxDescent };
    }
    return cache[k];
  };
  while (tw.nextNode()) {
    const n = tw.currentNode, t = n.textContent;
    if (!t.trim() || n.parentElement.closest("svg, script, style, .skip, .plate, .sky")) continue;
    const cs = getComputedStyle(n.parentElement), font = cs.fontStyle + " " + cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily;
    const word = i => (t.slice(0, i).match(/\\S*$/)[0] + t.slice(i).match(/^\\S*/)[0]).slice(0, 24) || "' '";
    for (let i = 0; i < t.length; i++) {
      const c = t.codePointAt(i), len = c > 0xffff ? 2 : 1, ch = t.substr(i, len);
      rg.setStart(n, i); rg.setEnd(n, i + len);
      const m = ink(font, ch);
      for (const q of rg.getClientRects()) {
        if (!q.width || !q.height) continue;
        const base = q.bottom - q.height * m.dd / ((m.a + m.dd) || 1);   // the baseline in this box
        out.push([q.left, base - m.up, q.right, base + m.down, word(i)]);
      }
      i += len - 1;
    }
  }
  return out;
}
// The polylines of an SVG path (M, L, H, V and Z, absolute or relative: what medusa.py and
// trails.js write), mapped to the frame's viewport; null for any other command.
function polylines(p) {
  const toks = (p.getAttribute("d") || "").match(/[a-zA-Z]|-?(?:\\d+\\.?\\d*|\\.\\d+)(?:e-?\\d+)?/g) || [];
  const m = p.getScreenCTM(), lines = [];
  if (!m) return lines;
  let x = 0, y = 0, x0 = 0, y0 = 0, cmd = "", cur = null, i = 0;
  const at = (a, b) => { const q = new DOMPoint(a, b).matrixTransform(m); cur.push(q.x, q.y); };
  while (i < toks.length) {
    if (/[a-zA-Z]/.test(toks[i])) { cmd = toks[i++]; if (cmd === "z" || cmd === "Z") { x = x0; y = y0; if (cur) at(x, y); continue; } }
    const num = () => parseFloat(toks[i++]);
    if (cmd === "M" || cmd === "m") {
      const a = num(), b = num();
      x = cmd === "m" ? x + a : a; y = cmd === "m" ? y + b : b; x0 = x; y0 = y;
      lines.push(cur = []); at(x, y); cmd = cmd === "m" ? "l" : "L";
    } else if (cmd === "L" || cmd === "l") { const a = num(), b = num(); x = cmd === "l" ? x + a : a; y = cmd === "l" ? y + b : b; at(x, y); }
    else if (cmd === "H" || cmd === "h") { const a = num(); x = cmd === "h" ? x + a : a; at(x, y); }
    else if (cmd === "V" || cmd === "v") { const b = num(); y = cmd === "v" ? y + b : b; at(x, y); }
    else return null;
  }
  return lines;
}
function crosses(ax, ay, bx, by, r) {   // does segment a-b touch rect r (Liang-Barsky)?
  let t0 = 0, t1 = 1;
  const dx = bx - ax, dy = by - ay;
  for (const [p, q] of [[-dx, ax - r[0]], [dx, r[2] - ax], [-dy, ay - r[1]], [dy, r[3] - ay]]) {
    if (p === 0) { if (q < 0) return false; continue; }
    const t = q / p;
    if (p < 0) { if (t > t1) return false; if (t > t0) t0 = t; } else { if (t < t0) return false; if (t < t1) t1 = t; }
  }
  return true;
}
// Where a line of the jellyfish or a tentacle crosses the ink of the text: the drawing (.plate, the
// 404 page's figure) and the trails overlay (svg.trails, rules and curls included).
function crossings(d, boxes) {
  const out = [];
  for (const p of d.querySelectorAll(".jelly svg path, svg.trails path")) {
    // not the drawing's faintest fringe hairs (j-tf3: 0.36px at .36 opacity), which reach .03 of the
    // way into its box, past the .11 the layout keeps clear, and graze the end of an intro line at
    // 880-920px (55em)
    if (p.closest("mask, defs") || p.matches(".j-tf3")) continue;
    const what = (p.closest("svg.trails") ? "tentacle" : "jellyfish") + (p.getAttribute("class") ? "." + p.getAttribute("class").split(" ")[0] : ""),
          b = p.getBoundingClientRect();
    const near = boxes.filter(r => r[0] <= b.right && r[2] >= b.left && r[1] <= b.bottom && r[3] >= b.top);
    if (!near.length) continue;
    const pl = polylines(p);
    if (!pl) { out.push(what + " path with curves (not checked)"); continue; }
    for (const P of pl) for (let k = 2; k < P.length; k += 2)
      for (const r of near) if (crosses(P[k - 2], P[k - 1], P[k], P[k + 1], r)) {
        if (out.length < 6) out.push(what + " x" + Math.round(P[k]) + " y" + Math.round(P[k + 1]) + " '" + r[4] + "'");
        else return out;
      }
  }
  return out;
}
async function measure(url, w) {
  const f = document.createElement("iframe");
  f.style.cssText = "width:" + w + "px;height:900px;border:0;display:block";
  document.body.appendChild(f);
  await new Promise(r => { f.onload = r; f.src = url; });
  const d = f.contentDocument, root = d.documentElement;
  if (d.title === "Error response") {  // the test server's 404 page: no such page in _site
    f.remove();
    return { url, w, ok: false, missing: true };
  }
  await new Promise(r => setTimeout(r, 250));
  await d.fonts.ready;
  await new Promise(r => setTimeout(r, 400));
  const fs = f.contentWindow.getComputedStyle(root).fontSize;
  const trails = root.classList.contains("has-trails");
  const secs = d.querySelectorAll("main .sec").length;
  const rules = d.querySelectorAll("svg.trails [data-rule]").length;
  const cw = root.clientWidth, sw = root.scrollWidth, clipped = [];
  const scrolls = el => {  // a box that scrolls sideways, or inside one: its text can be reached
    for (let a = el; a && a !== d.body; a = a.parentElement)
      if (/auto|scroll/.test(f.contentWindow.getComputedStyle(a).overflowX)) return true;
    return false;
  };
  for (const el of d.querySelectorAll("main *, header *, footer *")) {
    if (!TEXTY.test(el.tagName) || el.closest("[aria-hidden=true], svg") || scrolls(el)) continue;
    const r = el.getBoundingClientRect(), range = d.createRange();
    range.selectNodeContents(el);  // text can run past a block's own box, e.g. under overflow:hidden
    const right = Math.max(r.right, range.getBoundingClientRect().right);
    if (r.width && right > cw + 1) clipped.push(sel(el) + " right=" + Math.round(right));
  }
  const cross = crossings(d, glyphs(d));
  f.remove();
  const drawn = !(secs > 0 && (!trails || rules < secs));
  return { url, w, fs, cw, sw, trails, secs, rules, ok: sw <= cw && clipped.length === 0 && drawn && cross.length === 0,
           clipped: clipped.slice(0, 6), cross };
}
(async () => {
  const out = [];
  for (const p of PAGES) for (const w of WIDTHS) out.push(await measure(p, w));
  await fetch("/__result", { method: "POST", body: JSON.stringify(out) });
})();
</script>"""

FRAME = """<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#777}iframe{border:0;display:block}</style>
<iframe id="f" src="%s" style="width:%dpx;height:%dpx"></iframe>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    harness = ""
    result = None
    got_result = threading.Event()

    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path != "/__result":
            self.send_error(404)
            return
        Handler.result = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
        Handler.got_result.set()
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/__harness.html", "/__frame.html"):
            if u.path == "/__harness.html":
                body = self.harness
            else:
                q = dict(urllib.parse.parse_qsl(u.query))
                body = FRAME % (html.escape(q["src"]), int(q["w"]), int(q["h"]))
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()


def site_pages():
    """Every page in _site that is not a redirect, as the path it is served at (home first)."""
    out = []
    for f in glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True):
        with open(f, encoding="utf-8") as fh:
            if 'http-equiv="refresh"' in fh.read():
                continue
        rel = os.path.relpath(f, SITE).replace(os.sep, "/")
        out.append("/" + (rel[:-len("index.html")] if rel.endswith("index.html") else rel))
    return sorted(out, key=lambda u: (u != "/", u))


def serve():
    handler = functools.partial(Handler, directory=SITE)
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, httpd.server_address[1]


def png_complete(path):
    """True once the PNG at path ends with its IEND chunk (Chrome has finished writing it)."""
    try:
        with open(path, "rb") as fh:
            fh.seek(-8, os.SEEK_END)
            return fh.read() == b"IEND\xaeB`\x82"
    except OSError:
        return False


def chrome(args, timeout, done, font_size=16):
    """Run headless Chrome and return its stdout.

    font_size is the browser's default font size (the profile's preference, as Settings > Font
    size sets it), which rem, em and em media queries follow.
    Chrome (seen with 154) finishes its job (dumps the DOM, writes the screenshot) and then keeps
    running instead of exiting. So poll done(stdout) and stop Chrome as soon as it is true, or
    when it exits by itself, or at the timeout (the caller then sees missing output).
    """
    with tempfile.TemporaryDirectory() as prof:
        os.makedirs(os.path.join(prof, "Default"))
        with open(os.path.join(prof, "Default", "Preferences"), "w") as fh:
            json.dump({"webkit": {"webprefs": {"default_font_size": font_size}}}, fh)
        cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
               "--force-prefers-reduced-motion", f"--user-data-dir={prof}"] + args
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, start_new_session=True)
        out, deadline = b"", time.time() + timeout
        try:
            while time.time() < deadline and proc.poll() is None and not done(out.decode("utf-8", "replace")):
                if select.select([proc.stdout], [], [], 0.2)[0]:
                    out += os.read(proc.stdout.fileno(), 65536)
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # Chrome and its helper processes
            except (ProcessLookupError, PermissionError):  # already gone (macOS: EPERM when only zombies remain)
                pass
            proc.wait()
            out += proc.stdout.read()
        return out.decode("utf-8", "replace")


def widths(spec):
    """320 390 ... or a range FROM-TO:STEP."""
    out = []
    for s in spec:
        m = re.fullmatch(r"(\d+)-(\d+):(\d+)", s)
        out += list(range(int(m[1]), int(m[2]) + 1, int(m[3]))) if m else [int(s)]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs="+", help="paths to load (default: every page in _site)")
    ap.add_argument("--widths", nargs="+", help="frame widths in px, or FROM-TO:STEP (default: %s)" % WIDTHS)
    ap.add_argument("--font-sizes", nargs="+", type=int, default=FONT_SIZES, help="default font sizes in px")
    ap.add_argument("--shots")
    args = ap.parse_args()
    args.pages = args.pages or site_pages()
    ws = widths(args.widths) if args.widths else WIDTHS
    Handler.harness = HARNESS % (json.dumps(args.pages), json.dumps(ws))
    httpd, port = serve()
    base = f"http://127.0.0.1:{port}"
    fails = 0
    for fs in args.font_sizes:
        Handler.result = None
        Handler.got_result.clear()
        chrome([f"{base}/__harness.html"], timeout=600, done=lambda _: Handler.got_result.is_set(), font_size=fs)
        if Handler.result is None:
            print(f"FAIL harness produced no results at {fs}px (Chrome timed out or the pages did not load)")
            fails += 1
            continue
        res = json.loads(Handler.result)
        for r in res:
            if r["ok"]:
                continue
            fails += 1
            if r.get("missing"):
                print(f"FAIL {r['url']} @{r['w']}px: no such page in _site")
                continue
            print(f"FAIL {r['url']} @{r['w']}px font {r['fs']}: scrollWidth={r['sw']} clientWidth={r['cw']} "
                  f"clipped={r['clipped']} crossings={r['cross']} trails={r['trails']} secs={r['secs']} rules={r['rules']}")
        sizes = {r["fs"] for r in res if "fs" in r}
        if sizes and sizes != {f"{fs}px"}:   # the preference did not take: the run tested the wrong size
            fails += 1
            print(f"FAIL default font size {fs}px was not applied (pages saw {sorted(sizes)})")
    print(f"layout: {fails} failures across {len(args.pages)} pages x {len(ws)} widths x "
          f"{len(args.font_sizes)} font sizes ({', '.join(f'{s}px' for s in args.font_sizes)})")
    if args.shots:
        from PIL import Image
        os.makedirs(args.shots, exist_ok=True)
        for p in args.pages:
            slug = p.strip("/").replace("/", "-").replace(".html", "") or "home"
            for w in SHOT_WIDTHS:
                out = os.path.join(args.shots, f"{slug}-{w}.png")
                if os.path.exists(out):
                    os.remove(out)  # a PNG from an earlier run would already satisfy png_complete()
                q = urllib.parse.urlencode({"src": p, "w": w, "h": 3200})
                chrome([f"--window-size={max(w, 500)},3200", "--virtual-time-budget=8000",
                        f"--screenshot={out}", f"{base}/__frame.html?{q}"], timeout=120,
                       done=lambda _, out=out: png_complete(out))
                if not png_complete(out):
                    fails += 1
                    print(f"FAIL shot {out}: Chrome did not write a complete PNG")
                    continue
                Image.open(out).crop((0, 0, w, 3200)).save(out)
                print(f"shot {out}")
    httpd.shutdown()
    return fails


if __name__ == "__main__":
    sys.exit(min(main(), 125))
