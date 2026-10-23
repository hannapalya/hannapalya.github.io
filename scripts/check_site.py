#!/usr/bin/env python3
"""Static checks for the built site.

  python3 scripts/check_site.py              # build (scripts/build_local.sh), then check _site/
  python3 scripts/check_site.py --no-build   # check the existing _site/
  python3 scripts/check_site.py --external   # also request every external link (slow)

Prints PASS/FAIL per check, and WARN for what a post may say in passing (see check_pages).
Exit status = number of failed checks (at most 125).

The home, crochet and blog checks are made against the site's own data as built (_data/*.yml,
_config.yml, index.md, _posts/), so editing the content as README.md describes keeps them passing.
They check that each entry is shown whole and that the places that repeat a fact agree: the
tagline, the JSON-LD and the intro on role, employer and city; the links under the intro and the
JSON-LD sameAs; the X link and the twitter: tags. Only the content rules are fixed (DEGREE,
UNPUBLISHED, MUST_NOT_SAY_TEXT and the terms in the untracked .superpowers/must-not-say.txt), with
the retired wording, the phrases the intro must say (MUST_SAY) and the names it must link
(INTRO_LINKS), the search description (DESCRIPTION), the "other projects" line (OTHER_PROJECTS) and
the Scholar link's text, "Google Scholar".
"""
import argparse, glob, gzip, html, html.parser, json, math, os, re, subprocess, sys
import urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "_site")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
ALLOWED_BUILD_NOISE = ("No GitHub API authentication", "faraday-retry")

# ---- The content rules (current-requirements.md). These stay true whatever the content is. ----
# Never claim a degree. (The PhD is mentioned as under way and paused, which is fine.) Matched like
# MUST_NOT_SAY below: a FAIL on the site's own pages, a WARN on a post.
DEGREE = [re.compile(r"\b(?:B\.?Sc|M\.?Sc|B\.?A|M\.?A|MPhil|DPhil|MRes)\b"), "bachelor", "bachelor's",
          "master's", "degree", "graduated", "has a PhD", "holds a PhD", re.compile(r"\bDr\.? H")]
# Never mention unpublished work. Generic markers here; more terms can be listed in the untracked
# file PRIVATE_TERMS (below).
UNPUBLISHED = ["forthcoming", "in preparation", "in prep", "under review", "unpublished", "submitted to"]
# No "Research Scholar" in any page's text, meta tags or JSON-LD (posts included).
MUST_NOT_SAY_TEXT = ["Research Scholar"]
# Terms to say nowhere: not in the built site, nor in any file of the repo (pages, layouts, _data/,
# _config.yml, the READMEs, scripts). They are the terms under the "[nowhere]" line of PRIVATE_TERMS
# (below), so no file of the repo lists them; filled in main(). Without any, check_nowhere prints SKIP.
NOWHERE = []
NOWHERE_SKIP = (".git", ".superpowers", os.path.join("docs", "superpowers"), "vendor", ".jekyll-cache",
                ".sass-cache", ".bundle")   # not the repo's files: git, local notes, installed gems, caches
# The intro (index.md) says what she does now, where she is based and what she did before, in these
# words. The built page shows the apostrophe of "I'm" as U+2019 (kramdown's smart quotes), as in
# the paragraph's other "I'm", so that is the character the sentence is matched with.
MUST_SAY = ["threat modelling for AI-enabled biological risks", "I\u2019m based in London.", "Fourth Eon Biosecurity",
            "Centre for Long-Term Resilience", "on pause from a PhD", "Institute for Global Pandemic Planning",
            "St Andrews", "I studied biology and philosophy at the University of St Andrews.",
            "where I worked on early outbreak detection from symptom-based data."]
# Links in the intro, as (the words linked, url): the organisations of the paragraph about before GovAI
# (Addendum 26). The link is the name itself, so "the" in "the Centre for Long-Term Resilience" is not linked.
INTRO_LINKS = [("Fourth Eon Biosecurity", "https://fourtheon.bio"),
               ("Centre for Long-Term Resilience", "https://www.longtermresilience.org")]
# The home page's search and link-preview description (`description:` in _config.yml, Addendum 27): the
# <meta name="description"> and og:description say exactly this, in the intro's words. Change it here
# when you change that sentence.
DESCRIPTION = ("Hanna P\u00e1lya is a researcher at the Centre for the Governance of AI, where she works on "
               "threat modelling for AI-enabled biological risks.")
# The "other projects" section under writing (#projects): one line of these links, as (name, url), in
# this order and with nothing else. Its content is _data/other_projects.yml; add a project to both.
OTHER_PROJECTS = [("Cliver", "https://cliver.bio"),
                  ("Estimation Game", "https://www.quantifiedintuitions.org/estimation-game")]

# Retired wording. None of it may appear on the site's own pages (FIXED): not in their visible text,
# meta tags, JSON-LD, link and image URLs, alt text or comments. A string matches as a whole word or
# phrase, ignoring case; a compiled pattern is used as it is. Posts are prose and may use these words
# in passing, so on a post a match is only a WARN.
MUST_NOT_SAY = ["Oxford", "Blog post 1", "minima", "PhD student", "Palya H", "Fun_presentation",
                "headshot", "Lorem", "TODO", "TBD", "Barnsley",
                # the book-interior edition is gone: no part numbers, backlist, series line or subtitle
                "Also by", re.compile(r"\bPart [IVX]+\b"), re.compile(r"Selected work, 20\d\d", re.I),
                "Research on AI and biological risk",
                # the one-line summaries that were under each writing entry (Addenda 11 and 18) are gone
                # (Addendum 21); matched without the full stop, so they stay out however the entry ends
                "Asks how far open-weight AI models lag behind closed-weight ones in biological capabilities, "
                "and why that matters for safeguards",
                "A proposed research programme to screen DNA orders by what the sequences do, not only by "
                "what they resemble",
                "Tests whether AI models can check DNA synthesis customers as accurately as human reviewers, "
                "and at what cost",
                "Simulates how quickly hospital sequencing could detect a new respiratory pathogen, and what "
                "it would cost",
                "A policy memo on making DNA synthesis screening standard practice in the US",
                # the intro says "I'm based in London." (Addendum 22), not where she lives
                "I live in London",
                # the PhD clause is plainer (Addendum 26): "early outbreak detection from symptom-based data"
                "detecting pandemics earlier from syndromic surveillance data",
                # the search description says what the intro says (Addendum 27), not this earlier wording
                "studies how advances in AI could change biological risks"]
# More terms to keep off the site are listed, one per line, in this untracked file. Without it the
# check prints SKIP. Blank lines and lines starting with # are ignored. The terms before a line that
# says [nowhere] must not appear on the site's own pages (PRIVATE; a WARN on a post); the terms after
# it must not appear in any text file of the repo or the built site (NOWHERE, check_nowhere).
PRIVATE_TERMS = os.path.join(ROOT, ".superpowers", "must-not-say.txt")
PRIVATE = []   # filled from PRIVATE_TERMS in main()
RULES = [("claims a degree", DEGREE), ("mentions unpublished work", UNPUBLISHED),
         ("says a private term from .superpowers/must-not-say.txt", PRIVATE), ("mentions retired wording", MUST_NOT_SAY)]
FIXED = ("index.html", "404.html", "crochet/index.html", "blog/index.html")   # the site's own pages
# the fonts of earlier editions: only Quicksand is declared or named (check_fonts)
OLD_FONTS = ("Spectral", "PT Mono", "Inter Tight")
# the jellyfish is moonlight: no red in the stylesheet (\bember: the --ember tokens, not "remember")
RED = (r"#C2333A\b", r"#A51D25\b", r"\bember")
SOFT_EXTERNAL = ("linkedin.com", "x.com", "twitter.com", "scholar.google.com")  # bot-blocked: report, don't fail

FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f"  -- {detail}"))
    if not ok:
        FAILS.append(name)


def focusable(tag, a):
    """Whether an element is in the tab order: what an aria-hidden subtree must not contain."""
    if a.get("tabindex") is not None:
        try:
            return int(a["tabindex"]) >= 0
        except ValueError:   # an invalid tabindex is ignored
            pass
    if tag in ("button", "input", "select", "textarea") and "disabled" in a:
        return False
    if tag in ("a", "area"):
        return "href" in a or "xlink:href" in a
    if tag == "input":
        return (a.get("type") or "").lower() != "hidden"
    if tag in ("audio", "video"):
        return "controls" in a
    if "contenteditable" in a and (a["contenteditable"] or "").lower() != "false":
        return True
    return tag in ("button", "select", "textarea", "iframe", "summary")


class Page(html.parser.HTMLParser):
    """Collects links, images, ids, headings, text, JSON-LD and nesting errors; the links (<a>) with
    their accessible names, in document order; where </main> is; and anything focusable inside an
    aria-hidden subtree."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.errors, self.links, self.imgs, self.ids = [], [], [], [], []
        self.tags, self.h1, self.text, self.jsonld, self._in_ld = [], 0, [], [], False
        self.comments, self._in_code = [], False
        # self._hidden runs alongside self.stack: whether each open element is in an aria-hidden subtree
        self._hidden, self.hidden_focus = [], []
        # each <a>: its attributes, its index in self.tags and its accessible name (aria-label, or else
        # its text without aria-hidden descendants); main_end is the index in self.tags of </main>
        self.anchors, self._a, self.main_end = [], None, None

    def _record(self, tag, a):
        """Records a start tag; returns whether the element is in an aria-hidden subtree."""
        hidden = bool(self._hidden and self._hidden[-1]) or (a.get("aria-hidden") or "").lower() == "true"
        if hidden and focusable(tag, a):
            self.hidden_focus.append(f"<{tag}{' href=' + a['href'] if a.get('href') else ''}>")
        if tag == "a":
            self._a = {"attrs": a, "at": len(self.tags), "hidden": hidden, "depth": len(self.stack), "text": []}
            self.anchors.append(self._a)
        self.tags.append((tag, a))
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        if tag in ("a", "link") and a.get("href"):
            self.links.append(a["href"])
        if tag in ("img", "script", "source", "iframe") and a.get("src"):
            self.links.append(a["src"])
        if tag in ("img", "source") and a.get("srcset"):
            self.links += [c.split()[0] for c in a["srcset"].split(",") if c.strip()]
        if tag == "img":
            self.imgs.append(a)
        return hidden

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        hidden = self._record(tag, a)
        self._in_ld = tag == "script" and a.get("type") == "application/ld+json"
        self._in_code = tag in ("script", "style") and not self._in_ld
        if tag not in VOID:
            self.stack.append(tag)
            self._hidden.append(hidden)

    def handle_startendtag(self, tag, attrs):
        self._record(tag, dict(attrs))
        if tag == "a":   # <a/> has no content
            self._a = None

    def handle_endtag(self, tag):
        self._in_ld = self._in_code = False
        if tag == "main":
            self.main_end = len(self.tags)
        if tag in VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unexpected </{tag}>, open: {self.stack[-3:]}")
            if tag in self.stack:
                while self.stack.pop() != tag:
                    pass
        del self._hidden[len(self.stack):]
        if self._a and len(self.stack) <= self._a["depth"]:
            self._a = None

    def handle_data(self, data):
        if self._in_ld:
            self.jsonld.append(data)
        elif not self._in_code:   # the text of the page (and its <title>), not inline CSS or scripts
            self.text.append(data)
            if self._a and (self._a["hidden"] or not self._hidden[-1]):
                self._a["text"].append(data)

    def name(self, anchor):
        """The accessible name of a link: its aria-label, or else its text, spaces collapsed."""
        label = (anchor["attrs"].get("aria-label") or "").strip()
        return label or re.sub(r"\s+", " ", "".join(anchor["text"])).strip()

    def handle_comment(self, data):
        self.comments.append(data)

    @property
    def plain(self):
        return re.sub(r"\s+", " ", " ".join(self.text))


def parse(path):
    with open(path, encoding="utf-8") as fh:
        return parse_html(fh.read())


def parse_html(text):
    p = Page()
    p.feed(text)
    p.close()
    return p


def site_path(url_path):
    """Map a site URL path to a file in _site, or None."""
    rel = urllib.parse.unquote(url_path).lstrip("/")
    cands = [rel] if rel else []
    if rel == "" or rel.endswith("/"):
        cands = [rel + "index.html"]
    else:
        cands += [rel + "/index.html", rel + ".html"]
    for c in cands:
        f = os.path.join(SITE, c)
        if os.path.isfile(f):
            return f
    return None


def read_site(rel):
    """Text of a file in _site, or "" when it is missing (the check then FAILs instead of crashing)."""
    try:
        with open(os.path.join(SITE, rel), encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def is_redirect(path):
    with open(path, encoding="utf-8") as fh:
        return 'http-equiv="refresh"' in fh.read()


def lum(hexc):
    h = hexc.strip().lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tokens(block):
    return dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})\b", block))


def build():
    env = dict(os.environ)
    proc = subprocess.run([os.path.join(ROOT, "scripts", "build_local.sh")], cwd=ROOT, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout)
    noisy = [l.strip() for l in out.splitlines()
             if re.search(r"warn|error|deprecat", l, re.I) and not any(n in l for n in ALLOWED_BUILD_NOISE)]
    check("build: jekyll exits 0", proc.returncode == 0, out[-2000:])
    check("build: no warnings or errors", not noisy, "; ".join(noisy[:5]))
    return proc.returncode == 0


def check_files():
    need = ["index.html", "404.html", "blog/index.html", "crochet/index.html", "projects/index.html",
            "papers/index.html", "feed.xml", "sitemap.xml", "CNAME", "assets/css/site.css", "assets/css/fonts.css",
            "assets/img/hanna.jpg", "assets/img/social-card.png", "assets/favicon/favicon.svg",
            "assets/favicon/favicon.ico", "assets/favicon/favicon-96x96.png", "assets/favicon/apple-touch-icon.png",
            "assets/favicon/web-app-manifest-192x192.png", "assets/favicon/web-app-manifest-512x512.png",
            "assets/favicon/site.webmanifest", "favicon.ico"]
    missing = [n for n in need if not os.path.isfile(os.path.join(SITE, n))]
    check("files: required outputs exist", not missing, ", ".join(missing))
    banned = ["Fun_presentation.gif", "assets/Fun_presentation.gif", "assets/main.css", "assets/css/style.css",
              "README.html", "scripts", "docs", "vendor", "assets/images", "assets/Picture 1.jpg"]
    present = [b for b in banned if os.path.exists(os.path.join(SITE, b))]
    check("files: removed or excluded paths are absent", not present, ", ".join(present))
    check("files: CNAME is hannapalya.com", read_site("CNAME").strip() == "hannapalya.com")
    big = []
    for f in glob.glob(os.path.join(SITE, "**", "*"), recursive=True):
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico")) and os.path.getsize(f) > 200 * 1024:
            big.append(f"{os.path.relpath(f, SITE)} {os.path.getsize(f) // 1024}KB")
    check("files: every image under 200 KB", not big, ", ".join(big))
    home = os.path.join(SITE, "index.html")
    size = os.path.getsize(home) if os.path.isfile(home) else 0
    check("files: home HTML under 200 KB", 0 < size < 200 * 1024, f"{size // 1024} KB")
    gz = len(gzip.compress(open(home, "rb").read())) if size else 0
    check("files: home HTML under 80 KB gzipped", 0 < gz < 80 * 1024, f"{gz // 1024} KB")


def check_pages():
    pages = [f for f in glob.glob(os.path.join(SITE, "**", "*.html"), recursive=True) if not is_redirect(f)]
    parsed = {}
    for f in pages:
        rel = os.path.relpath(f, SITE)
        fixed = rel in FIXED
        p = parsed[f] = parse(f)
        raw = open(f, encoding="utf-8").read()
        check(f"{rel}: well-formed", not p.errors and not [t for t in p.stack if t not in ("html", "body")],
              "; ".join(p.errors[:3]) + f" unclosed={p.stack}")
        check(f"{rel}: exactly one <h1>", p.h1 == 1, f"found {p.h1}")
        check(f"{rel}: <html lang=en>", re.search(r'<html lang="en"', raw) is not None)
        check(f"{rel}: skip link + #main", "#main" in p.links and "main" in p.ids)
        dup = sorted({i for i in p.ids if p.ids.count(i) > 1})
        check(f"{rel}: no duplicate ids", not dup, ", ".join(dup))
        check(f"{rel}: nothing focusable inside aria-hidden", not p.hidden_focus, ", ".join(p.hidden_focus[:5]))
        check(f"{rel}: images have alt", not [i for i in p.imgs if not i.get("alt")],
              ", ".join(str(i.get("src")) for i in p.imgs if not i.get("alt")))
        unsized = [str(i.get("src")) for i in p.imgs if not i.get("width") or not i.get("height")]
        if fixed or not unsized:
            check(f"{rel}: images have width and height", not unsized, ", ".join(unsized))
        else:   # a post: Markdown's ![alt](src) gives no size; add {: width="…" height="…"} after it
            print(f"WARN {rel}: images without width and height (the page shifts as they load): {', '.join(unsized)}")
        check(f"{rel}: stylesheet linked", any(l.startswith("/assets/css/site.css") for l in p.links))
        # one theme: no toggle button and no script that picks a theme before the page paints
        head = raw.split("</head>")[0]
        check(f"{rel}: no theme toggle", 'class="theme"' not in raw and "localStorage" not in head
              and "data-theme" not in head)
        meta = [a.get("content", "") for t, a in p.tags if t == "meta"] + p.jsonld
        old = [w for w in MUST_NOT_SAY_TEXT if said(w, " \n".join([p.plain] + meta))]
        check(f"{rel}: does not say {', '.join(map(repr, MUST_NOT_SAY_TEXT))} (text, meta tags, JSON-LD)",
              not old, ", ".join(old))
        # The content rules, retired wording, the fern and the ground: a FAIL on the site's own pages,
        # a WARN on a post (prose may use these words in passing; read the WARN and decide).
        q = p
        if rel == "blog/index.html":   # its list is the posts' titles and links, which are checked as posts
            q = parse_html(re.sub(r'<ul class="list"[^>]*>.*?</ul>', "", raw, flags=re.S))
        words = " \n".join([q.plain] + [a.get("content", "") for t, a in q.tags if t == "meta"] + q.jsonld +
                            q.links + q.comments +
                            [a[k] for t, a in q.tags for k in ("alt", "title", "aria-label") if a.get(k)])
        found = []
        for what, terms in RULES:
            found += [f"{what} '{w if isinstance(w, str) else w.pattern}'" for w in terms if said(w, words)]
        if re.search(r"\bfern\b", raw, re.I):   # the fern is gone: no drawing, mark, class or note
            found.append("mentions retired wording 'fern'")
        # the ground at the foot of the page is gone: no horizon line and no dark footer band
        found += [f"has the ground '{w}'" for w in (r'class="[^"]*\bhorizon\b', 'class="back"') if re.search(w, raw)]
        if fixed and not found:
            check(f"{rel}: content rules; no retired wording, fern or ground", True)
        for w in found:
            if fixed:
                check(f"{rel}: {w}", False)
            else:
                print(f"WARN {rel}: {w} (fine in a post if meant)")
    return parsed


def said(term, text):
    """Whether text says term: a string as a whole word or phrase, ignoring case; a pattern as it is."""
    if isinstance(term, re.Pattern):
        return term.search(text) is not None
    return re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I) is not None


def read_terms():
    """Fills PRIVATE and NOWHERE from PRIVATE_TERMS: the terms before a "[nowhere]" line go to PRIVATE,
    the terms after it to NOWHERE."""
    terms = PRIVATE
    with open(PRIVATE_TERMS, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line == "[nowhere]":
                terms = NOWHERE
            elif line and not line.startswith("#"):
                terms.append(line)


def check_nowhere():
    """NOWHERE: every text file in the repo and in the built site (this script included)."""
    if not NOWHERE:
        print(f"SKIP nowhere terms (none under [nowhere] in {os.path.relpath(PRIVATE_TERMS, ROOT)})")
        return
    found = []
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = [x for x in dirs if os.path.relpath(os.path.join(d, x), ROOT) not in NOWHERE_SKIP]
        for name in files:
            f = os.path.join(d, name)
            try:
                with open(f, "rb") as fh:
                    data = fh.read()
                if b"\0" in data:   # a binary file: images, fonts
                    continue
                text = data.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            found += [f"{os.path.relpath(f, ROOT)}: {w}" for w in NOWHERE if said(w, text)]
    check(f"nowhere: the {len(NOWHERE)} terms under [nowhere] (the repo and the built site)", not found,
          "; ".join(found[:8]))


def built_posts():
    """The posts Jekyll built (not the files in _posts/: a future-dated or unpublished one is not built)."""
    return glob.glob(os.path.join(SITE, "blog", "*", "*", "index.html"))


def check_links(parsed):
    broken = []
    for f, p in parsed.items():
        base = "/" + os.path.relpath(f, SITE).replace("index.html", "")
        for link in p.links:
            if link.startswith(("mailto:", "data:", "http://", "https://", "//")):
                continue
            u = urllib.parse.urlparse(urllib.parse.urljoin(base, link))
            target = site_path(u.path) if u.path else f
            if not target:
                broken.append(f"{os.path.relpath(f, SITE)} -> {link}")
                continue
            if u.fragment and target.endswith(".html"):
                tp = parsed.get(target) or parse(target)
                if u.fragment not in tp.ids:
                    broken.append(f"{os.path.relpath(f, SITE)} -> {link} (no id)")
    check("links: internal links and fragments resolve", not broken, "; ".join(broken[:8]))


def untag(fragment):
    """The text of an HTML fragment, with spaces collapsed."""
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", fragment))).strip()


def items(fragment):
    """Each <li> in an HTML fragment as (text, hrefs)."""
    return [(untag(li), [html.unescape(h) for h in re.findall(r'href="([^"]*)"', li)])
            for li in re.findall(r"<li\b.*?</li>", fragment, re.S)]


def entries(name):
    """How many entries _data/<name>.yml has (top-level list items: lines that start with '- ')."""
    try:
        with open(os.path.join(ROOT, "_data", name + ".yml"), encoding="utf-8") as fh:
            return sum(1 for l in fh if l.startswith("- "))
    except OSError:
        return 0


def ruby_yaml(path):
    """A YAML file read with Ruby's YAML, as Jekyll reads it: (data, None), or (None, an error message)
    when it does not parse."""
    try:
        out = subprocess.run(["ruby", "-ryaml", "-rjson", "-e", "print JSON.generate(YAML.load_file(ARGV[0]))", path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return (json.loads(out.stdout), None) if out.returncode == 0 else (None, out.stderr.strip()[-300:])
    except (OSError, ValueError) as e:
        return None, str(e)


def stars():
    """_data/stars.yml as a list of (label, url), read with Ruby's YAML as Jekyll reads it; or an error
    message when it is missing, does not parse, or is not a list of entries with a label and a url."""
    path = os.path.join(ROOT, "_data", "stars.yml")
    if not os.path.isfile(path):
        return "no _data/stars.yml"
    data, err = ruby_yaml(path)
    if err is not None:
        return f"_data/stars.yml does not parse: {err}"
    data = data or []   # an empty file: no stars
    if not isinstance(data, list) or not all(isinstance(d, dict) and d.get("label") and d.get("url") for d in data):
        return "_data/stars.yml is not a list of entries with a label and a url"
    return [(str(d["label"]), str(d["url"])) for d in data]


def jellyfish():
    """The jellyfish's link, jellyfish: in _config.yml, as (label, url); or an error message when it is
    missing or has no label or url."""
    data, err = ruby_yaml(os.path.join(ROOT, "_config.yml"))
    if err is not None:
        return f"_config.yml does not parse: {err}"
    j = data.get("jellyfish") if isinstance(data, dict) else None
    if not isinstance(j, dict) or not j.get("label") or not j.get("url"):
        return "no jellyfish: in _config.yml with a label and a url"
    return str(j["label"]), str(j["url"])


def check_home(parsed):
    """The home page, checked against its own data (_data/*.yml and _config.yml, as built), so editing
    the content as README.md describes keeps it passing; only the content rules are fixed."""
    f = os.path.join(SITE, "index.html")
    p = parsed[f]
    raw = open(f, encoding="utf-8").read()

    def sec(sid):
        m = re.search(r'<section\b[^>]*\bid="%s".*?</section>' % sid, raw, re.S)
        return m.group(0) if m else ""

    # two sections, "writing" and under it "other projects" (there is no work or "other things" section)
    secs = []
    for m in re.finditer(r"<section\b([^>]*)>(.*?)</section>", raw, re.S):
        sid, h2 = re.search(r'\bid="([^"]*)"', m.group(1)), re.search(r"<h2\b[^>]*>(.*?)</h2>", m.group(2), re.S)
        secs.append((sid.group(1) if sid else "", untag(h2.group(1)) if h2 else ""))
    check("home: two sections, #publications labelled 'writing', then #projects labelled 'other projects'",
          secs == [("publications", "writing"), ("projects", "other projects")], str(secs))
    # writing: one item per entry in _data/publications.yml, each just its linked title and the year, so
    # its text is exactly "<title> (<year>)": no summary, no trailing full stop. Only published work is
    # listed, so each links to where it was published (a DOI, or a post's page).
    pubs = items(sec("publications"))
    check("home: one publication per entry in _data/publications.yml",
          len(pubs) == entries("publications") > 0, f"{len(pubs)} items, {entries('publications')} entries")
    data, err = ruby_yaml(os.path.join(ROOT, "_data", "publications.yml"))
    data = [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []
    want = [f"{d.get('title')} ({d.get('year')})" for d in data]
    wrong = [f"{t!r} for {w!r}" for (t, _), w in zip(pubs, want) if t != w]
    check("home: each publication reads '<title> (<year>)', with no further sentence",
          bool(want) and len(pubs) == len(want) and not wrong,
          err or "; ".join(wrong[:3]) or f"{len(pubs)} items, {len(want)} entries")
    check("home: every publication links to where it was published",
          bool(pubs) and all(any(h.startswith("http") for h in hrefs) for _, hrefs in pubs),
          "; ".join(t[:40] for t, hrefs in pubs if not any(h.startswith("http") for h in hrefs)))
    nosum = [str(d.get("title"))[:40] for d in data if "summary" in d]
    check("data: no entry in _data/publications.yml has a summary", not nosum, "; ".join(nosum))
    # the list ends with its last entry: Scholar is in the links line under the intro, not under writing
    check("home: no 'all on Google Scholar' link", not said("all on Google Scholar", p.plain))
    empty = re.findall(r'<span class="muted">\s*</span>|\(\)|\. \.', raw.split("<body", 1)[-1])
    check("home: no empty descriptions or dangling punctuation", not empty, ", ".join(empty))
    # other projects: one paragraph, the links in OTHER_PROJECTS separated by "·" (as in the links line
    # under the intro), with no descriptions
    op = sec("projects")
    q = parse_html(op)
    links = [(q.name(a), a["attrs"].get("href")) for a in q.anchors]
    op_text = re.sub(r"\s+", " ", untag(re.sub(r"<h2\b.*?</h2>", "", op, flags=re.S)))
    want = " · ".join(name for name, _ in OTHER_PROJECTS)
    check(f"home: #projects is one line, '{want}', linked as in OTHER_PROJECTS",
          links == OTHER_PROJECTS and op_text == want and len(re.findall(r"<p\b", op)) == 1, f"{links}; {op_text!r}")
    # the contact links: one line under the intro, before the section, from email: and links: in _config.yml
    line = re.search(r'<p class="links">(.*?)</p>', raw, re.S)
    hrefs = [html.unescape(h) for h in re.findall(r'href="([^"]*)"', line.group(1))] if line else []
    sec_at = raw.find("<section")
    check("home: contact links under the intro (before the section)", bool(hrefs) and 0 <= raw.find(line.group(0)) < sec_at)
    people = [d for d in (json.loads(x) for x in p.jsonld if x.strip()) if d.get("@type") == "Person"]
    person = people[0] if people else {}
    check("home: one JSON-LD Person", len(people) == 1, f"found {len(people)}")
    mail = [h for h in hrefs if h.startswith("mailto:")]
    check("home: the email under the intro is the JSON-LD email", len(mail) == 1 and mail[0] == person.get("email"),
          f"{mail} vs {person.get('email')}")
    profiles = [h for h in hrefs if not h.startswith("mailto:")]
    check("home: the profiles under the intro (links: in _config.yml) are the JSON-LD sameAs (social.links:)",
          bool(profiles) and sorted(profiles) == sorted(person.get("sameAs", [])),
          f"{sorted(set(profiles) ^ set(person.get('sameAs', [])))}")
    metas = {a.get("name") or a.get("property"): a.get("content", "") for t, a in p.tags if t == "meta"}
    xs = [h.rstrip("/").rsplit("/", 1)[-1] for h in profiles if re.match(r"https://(x|twitter)\.com/", h)]
    handles = {metas.get("twitter:site"), metas.get("twitter:creator")}
    check("home: twitter:site and twitter:creator are the X handle in the links",
          not xs or handles == {"@" + xs[0]}, f"{sorted(map(str, handles))} vs {xs}")
    # the search description and link previews say DESCRIPTION: both the plain and the Open Graph tag
    for tag in ("description", "og:description"):
        check(f"home: <meta {tag}> is the description in DESCRIPTION", metas.get(tag) == DESCRIPTION,
              f"{metas.get(tag)!r}")
    scholar = [h for h in profiles if "scholar.google" in h]
    # the Scholar link is worded "Google Scholar" (spec Addendum 23), not just "Scholar"
    ln = parse_html(line.group(0)) if line else None
    scholar_text = [ln.name(a) for a in ln.anchors if "scholar.google" in html.unescape(a["attrs"].get("href", ""))] if ln else []
    check("home: the Scholar link under the intro reads 'Google Scholar'", scholar_text == ["Google Scholar"], str(scholar_text))
    pap = read_site("papers/index.html")
    check("redirect: /papers/ -> the Scholar link", bool(scholar) and scholar[0] in html.unescape(pap)
          and 'http-equiv="refresh"' in pap, str(scholar))
    # role, employer and city: the tagline (_config.yml), the JSON-LD and the intro agree
    title = re.search(r"<title>(.*?)</title>", raw, re.S)
    tagline = html.unescape(title.group(1)).split(" | ", 1)[-1] if title else ""
    role, _, org = tagline.partition(", ")
    works = person.get("worksFor", {}).get("name")
    check("home: JSON-LD jobTitle and worksFor match the tagline (_config.yml)",
          bool(org) and person.get("jobTitle") == role and works == org,
          f"tagline {tagline!r}; JSON-LD {person.get('jobTitle')!r}, {works!r}")
    lede = re.search(r'<div class="lede-col">(.*?)<p class="links">', raw, re.S)
    intro = untag(lede.group(1)) if lede else ""
    city = person.get("homeLocation", {}).get("name", "")
    for what, text in (("intro (index.md)", intro), ("description (_config.yml)", metas.get("description", ""))):
        miss = [w for w in (role.lower(), org) if w.lower() not in text.lower()]
        check(f"home: the {what} gives the role and employer in the tagline", bool(org) and not miss, ", ".join(miss))
    check("home: the intro gives the city in the JSON-LD homeLocation", bool(city) and city in intro, city)
    missing = [w for w in MUST_SAY if w not in intro]
    check("home: the intro says what she does and did (MUST_SAY)", not missing, ", ".join(missing))
    # INTRO_LINKS: each name is a link of its own in the intro, to its site
    lp = parse_html(lede.group(1)) if lede else None
    in_intro = [(lp.name(a), html.unescape(a["attrs"].get("href", ""))) for a in lp.anchors] if lp else []
    unlinked = [f"{name} -> {url}" for name, url in INTRO_LINKS if (name, url) not in in_intro]
    check("home: the intro links each name in INTRO_LINKS to its site", not unlinked,
          "; ".join(unlinked) + f" (the intro links {in_intro})")
    # there is no projects page to link to from the top of the page: /projects/ redirects to #projects
    to_page = [l for l in p.links if l.split("#")[0].rstrip("/") == "/projects"]
    check("home: no link to /projects/", not to_page, ", ".join(to_page))
    # the illustration and what is not on the page
    plate = re.search(r'<div class="plate jelly-plate" aria-hidden="true">', raw)
    check("home: illustration plate is aria-hidden", plate is not None)
    check("home: night sky aria-hidden", '<div class="sky" aria-hidden="true">' in raw)
    # the secret stars: each entry of _data/stars.yml is a link with its url, whose accessible name is
    # its label, and the links come after </main>, so they are last in tab order (that none is inside
    # the aria-hidden sky is checked on every page: nothing focusable inside aria-hidden)
    sky = stars()
    if isinstance(sky, str):
        check("home: each star in _data/stars.yml is a link with its url, named by its label", False, sky)
        check("home: the star links come after </main>", False, sky)
    else:
        links = [(label, [a for a in p.anchors if a["attrs"].get("href") == url and p.name(a) == label])
                 for label, url in sky]
        missing = [label for label, found in links if not found]
        check("home: each star in _data/stars.yml is a link with its url, named by its label", not missing,
              "missing: " + ", ".join(missing) + (" (there are stars for 5 at most)" if len(sky) > 5 else ""))
        early = [label for label, found in links if any(p.main_end is None or a["at"] < p.main_end for a in found)]
        check("home: the star links come after </main>", p.main_end is not None and not early,
              ", ".join(early) or "no </main>")
    # the jellyfish's bell is a secret link like the stars: the url of jellyfish: in _config.yml, named
    # by its label, outside any aria-hidden subtree and after </main>
    jelly = jellyfish()
    if isinstance(jelly, str):
        check("home: the jellyfish is a link (jellyfish: in _config.yml)", False, jelly)
        check("home: the jellyfish link comes after </main>", False, jelly)
    else:
        label, url = jelly
        found = [a for a in p.anchors if a["attrs"].get("href") == url and p.name(a) == label and not a["hidden"]]
        check(f"home: the jellyfish is a link to {url} named '{label}', outside aria-hidden (jellyfish: in _config.yml)",
              bool(found), "missing")
        check("home: the jellyfish link comes after </main>",
              p.main_end is not None and not any(a["at"] < p.main_end for a in found), "no </main>" if p.main_end is None else "before")
    check("home: jellyfish with its gonads split out", "jl-bell" in raw and '<g class="gonads">' in raw)
    # the jellyfish is only its glowing line drawing: no static horizontal smear (a ghost of the bell
    # blurred sideways and cut into bands)
    smear = [w for w in ('class="smear', "smear-wrap") if w in raw]
    smear += [f'feGaussianBlur stdDeviation="{m.group(0)}"' for m in
              re.finditer(r'(?<=stdDeviation=")\s*[\d.]*[1-9][\d.]*[\s,]+0(?:\.0*)?\s*(?=")', raw)]
    check("home: no horizontal smear on the jellyfish", not smear, "; ".join(smear))
    # no bottom panel: no contact section, no ground and no photo (assets/img/hanna.jpg is only the
    # JSON-LD Person.image)
    body = raw.split("<body", 1)[-1]
    found = [w for w in ('id="contact"', 'class="back"', r'class="[^"]*\bhorizon\b', "<img") if re.search(w, body)]
    check("home: no contact section, ground or photo in <body>", not found, ", ".join(found))


def check_subpages(parsed):
    c = parsed.get(os.path.join(SITE, "crochet", "index.html"))
    if c:
        imgs = [i for i in c.imgs if i.get("src", "").startswith("/assets/img/crochet/")]
        raw = read_site("crochet/index.html")
        caps = [untag(x) for x in re.findall(r"<figcaption>(.*?)</figcaption>", raw, re.S)]
        check("crochet: one photo per entry in _data/crochet.yml, each with a caption",
              len(imgs) == len(caps) == entries("crochet") > 0 and all(caps),
              f"{len(imgs)} photos, {len(caps)} captions, {entries('crochet')} entries")
    b = parsed.get(os.path.join(SITE, "blog", "index.html"))
    posts = built_posts()
    if b:
        raw = read_site("blog/index.html")
        check("blog: headed 'writing'", '<h1 class="label">writing</h1>' in raw)
        if posts:
            n = len(re.findall(r"<li\b", raw))
            check("blog: lists every post", n == len(posts), f"{n} listed, {len(posts)} built")
        else:
            check("blog: empty state", "Nothing here yet." in b.plain)
    n = parsed.get(os.path.join(SITE, "404.html"))
    if n:
        raw = open(os.path.join(SITE, "404.html"), encoding="utf-8").read()
        check("404: jellyfish, note and home link", "jl-bell" in raw and "drifted off" in n.plain and "/" in n.links)
        jelly = jellyfish()
        check("404: the jellyfish links where the home page's does, named by its label",
              not isinstance(jelly, str) and any(a["attrs"].get("href") == jelly[1] and n.name(a) == jelly[0] and not a["hidden"]
                                                for a in n.anchors), jelly if isinstance(jelly, str) else "missing")
    # /projects/ was a page of its own; it now sends visitors to the "other projects" section on home
    proj = read_site("projects/index.html")
    check("redirect: /projects/ -> /#projects",
          re.search(r'http-equiv="refresh" content="0; url=(?:https://hannapalya\.com)?/#projects"', proj) is not None)
    for x in ("feed.xml", "sitemap.xml"):
        try:
            ET.parse(os.path.join(SITE, x))
            check(f"{x}: parses as XML", True)
        except (ET.ParseError, OSError) as e:
            check(f"{x}: parses as XML", False, str(e))
    sm = read_site("sitemap.xml")
    check("sitemap: lists /crochet/", "<loc>https://hannapalya.com/crochet/</loc>" in sm)
    # an empty Writing page stays out of the sitemap; with the first post, take `sitemap: false` out of blog.html
    check("sitemap: lists /blog/ only when there are posts", ("<loc>https://hannapalya.com/blog/</loc>" in sm) == bool(posts),
          "remove `sitemap: false` from blog.html" if posts else "")


def check_contrast():
    css = read_site("assets/css/site.css")
    m = re.search(r":root\s*\{([^}]*)\}", css)
    if not m:
        check("contrast: :root token block found", False)
        return
    t = tokens(m.group(1))
    for fg in ("--ink", "--muted", "--link"):
        if fg in t and "--paper" in t:
            r = contrast(t[fg], t["--paper"])
            check(f"contrast: {fg} on --paper >= 4.5", r >= 4.5, f"{r:.2f}")
        else:
            check(f"contrast: tokens {fg}/--paper defined", False)


def check_palette():
    css = read_site("assets/css/site.css")
    red = [w for w in RED if re.search(w, css, re.I)]
    check("css: no red (no ember tokens, #C2333A or #A51D25)", bool(css) and not red,
          ", ".join(w.replace("\\b", "") for w in red) or "no site.css")


def sparkle(d):
    """(x, y, r) of the four-pointed sparkle that the path data d draws, or None if it is not one: a
    closed M and four Q sides, its four tips equally far (r) from their centre (x, y) and a quarter
    turn apart, all the same way round, each side's control point nearer that centre than its chord's
    midpoint (so the sides curve in)."""
    v = [float(n) for n in re.findall(r"-?(?:\d+\.?\d*|\.\d+)", d)]
    if not re.fullmatch(r"\s*M[^A-Za-z]+(?:Q[^A-Za-z]+){4}Z\s*", d) or len(v) != 18 or v[:2] != v[16:]:
        return None
    tips, ctrl = [v[i:i + 2] for i in (0, 4, 8, 12)], [v[i:i + 2] for i in (2, 6, 10, 14)]
    x, y = sum(p[0] for p in tips) / 4, sum(p[1] for p in tips) / 4
    rel = [(px - x, py - y) for px, py in tips]
    r = sum(math.hypot(*p) for p in rel) / 4
    way = lambda a, b: a[0] * b[1] - a[1] * b[0] > 0
    for i in range(4):
        a, b, (qx, qy) = rel[i], rel[(i + 1) % 4], ctrl[i]
        if (abs(math.hypot(*a) - r) > .02 * r or abs(a[0] * b[0] + a[1] * b[1]) > .02 * r * r
                or way(a, b) != way(rel[0], rel[1])
                or math.hypot(qx - x, qy - y) >= math.hypot((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)):
            return None
    return x, y, r


def check_favicon():
    """The icon is a sparkle (Addendum 25): favicon.svg draws two closed four-pointed sparkles with
    inward-curving sides, a main one and a smaller one up and to its right, in --star on --paper."""
    svg = read_site("assets/favicon/favicon.svg")
    drawn = re.findall(r'<path\b[^>]*\bd="([^"]+)"', svg)
    found = sorted((s for s in map(sparkle, drawn) if s), key=lambda s: -s[2])
    ok = len(drawn) == len(found) == 2
    if ok:
        (mx, my, mr), (sx, sy, sr) = found
        ok = .2 <= sr / mr <= .5 and sx > mx and sy < my
    check("favicon: favicon.svg draws a sparkle and a smaller one up and to its right", ok,
          f"{len(drawn)} path(s), {len(found)} of them sparkles" if svg else "no favicon.svg")
    m = re.search(r":root\s*\{([^}]*)\}", read_site("assets/css/site.css"))
    t = tokens(m.group(1)) if m else {}
    star, paper = t.get("--star", "").upper(), t.get("--paper", "").upper()
    fills = [c.upper() for c in re.findall(r'<rect\b[^>]*\bfill="(#[0-9A-Fa-f]{6})"', svg)]
    marks = [c.upper() for c in re.findall(r'<path\b[^>]*\bfill="(#[0-9A-Fa-f]{6})"', svg)]
    colours = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", svg)}
    check("favicon: --star sparkles on --paper, no other colour, stroke or opacity",
          bool(star and paper) and fills == [paper] and marks == [star, star] and colours == {star, paper}
          and "stroke" not in svg and "opacity" not in svg,
          f"background {fills}, sparkles {marks}, want {paper} and {star}")


def check_fonts():
    families = set(re.findall(r"font-family:\s*'([^']+)'", read_site("assets/css/fonts.css")))
    check("fonts: fonts.css declares only Quicksand", families == {"Quicksand"}, ", ".join(sorted(families)))
    # no earlier edition's font named in the stylesheets or in the site's own pages (with their head)
    css = read_site("assets/css/site.css") + read_site("assets/css/fonts.css") + "".join(map(read_site, FIXED))
    old = [f for f in OLD_FONTS if f in css]
    check("fonts: no earlier font (Spectral, PT Mono, Inter Tight) named", not old, ", ".join(old))


def doi_registered(u):
    """doi.org redirects into publisher sites that challenge scripts with a 403 (SAGE does);
    the handle API still confirms the DOI itself is registered, so a mistyped DOI keeps failing."""
    try:
        api = "https://doi.org/api/handles/" + u.split("://doi.org/", 1)[1]
        return json.load(urllib.request.urlopen(api, timeout=20)).get("responseCode") == 1
    except Exception:
        return False


def check_external(parsed):
    urls = sorted({l for p in parsed.values() for l in p.links if l.startswith(("http://", "https://"))
                   and "hannapalya.com" not in l and "fonts." not in l})
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": ua}, method="GET")
            code = urllib.request.urlopen(req, timeout=20).status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception as e:  # network errors
            code = str(e)[:60]
        ok = isinstance(code, int) and code < 400
        if code == 403 and "://doi.org/" in u and doi_registered(u):
            print(f"PASS external: {u} (publisher blocks bots; DOI is registered)")
            continue
        if not ok and any(s in u for s in SOFT_EXTERNAL):
            print(f"SKIP external {u} ({code}; site blocks bots)")
            continue
        check(f"external: {u}", ok, str(code))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--external", action="store_true")
    args = ap.parse_args()
    if os.path.isfile(PRIVATE_TERMS):
        read_terms()
    else:
        print(f"SKIP private terms (no {os.path.relpath(PRIVATE_TERMS, ROOT)})")
    if not args.no_build and not build():
        print(f"\n{len(FAILS)} failed")
        return len(FAILS)
    check_files()
    check_nowhere()
    parsed = check_pages()
    check_links(parsed)
    if os.path.join(SITE, "index.html") in parsed:
        check_home(parsed)
    check_subpages(parsed)
    check_contrast()
    check_palette()
    check_favicon()
    check_fonts()
    if args.external:
        check_external(parsed)
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall checks passed")
    return len(FAILS)


if __name__ == "__main__":
    sys.exit(min(main(), 125))
