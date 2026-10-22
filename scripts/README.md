# Scripts

Nothing in this folder is published; Jekyll excludes it.

Python 3 is needed throughout. `medusa.py` also needs `numpy`; the image, favicon and social-card scripts need `Pillow`. `check_layout.py` and `social_card.py` need Google Chrome (set `CHROME` to use another path). Builds use the gems in the repo `Gemfile` on Ruby 3 or later, and on an older Ruby (macOS's built-in 2.6) the pinned gems in `dev/Gemfile`, which `dev/install.sh` installs into `vendor/dev/` in the repo (`gems.sh` makes the choice). Set `GEMS=dev` to use the pinned gems on any Ruby, or `JEKYLL_ENV_DIR` to a folder holding another `Gemfile` and `vendor/` to use those instead. For the Python scripts: `python3 -m pip install --user pillow numpy`.

| Script | What it does |
| --- | --- |
| `build_local.sh` | Builds the site into `_site/` with the GitHub Pages gem set. |
| `serve_local.sh` | Serves the site at http://localhost:4000 and rebuilds it when a file changes; extra arguments (such as `--port 4001`) go to `jekyll serve`. |
| `dev/install.sh` | Installs `dev/Gemfile` (github-pages 231, with the gems it pulls in pinned for Ruby 2.6 in `dev/Gemfile.lock`) into `vendor/dev/`. |
| `check_site.py` | Builds, then checks the pages, links, images, size budgets, contrast, colours, fonts, redirects and sitemap. The content checks follow the data: every publication and crochet photo is shown whole, and the places that repeat your role, employer, city and links agree with each other; the intro must also say each phrase in `MUST_SAY`, the "other projects" line must be exactly the links in `OTHER_PROJECTS`, and the Scholar link under the intro must read "Google Scholar". The content rules are fixed: no degree claimed, no unpublished work, no "Research Scholar", and no retired wording (a FAIL on the site's own pages, a WARN on a post). Extra terms to keep off the site can be listed in `.superpowers/must-not-say.txt`, one per line (untracked; without it the check prints SKIP). Terms after a `[nowhere]` line in that file are also searched for in every text file of the repo, not only in the built pages. `--external` also requests outside links; sites that block bots are reported as SKIP. |
| `check_layout.py` | Loads every page in headless Chrome at 320–1920px, at the browser's default text size (16px) and at 20px and 24px (Chrome's Large and Very large); fails on sideways scroll, clipped text, a line of the jellyfish or a tentacle crossing text, or section rules the trails script did not draw. `--widths 320-1920:10` sweeps every 10px, `--font-sizes 16` tests one size, and `--shots DIR` saves 390px and 1440px screenshots. |
| `fetch_fonts.py` | Downloads Quicksand (latin and latin-ext) into `assets/fonts/` and writes `assets/css/fonts.css`. |
| `medusa.py` | Moon jellyfish generator: recursive radial canals, frilled oral arms, tapered tentacles. Run by `build_illustrations.py`, not by hand. |
| `build_illustrations.py` | Runs `medusa.py` and writes the jellyfish layers, the bell mark, the stars and the speck and grain tiles to `_includes/illustrations/`. |
| `make_images.py` | Portrait and crochet photos from `originals/`; writes `_data/crochet.yml`. The portrait (`assets/img/hanna.jpg`) is not shown on the page, only used as the JSON-LD image; its source is `PORTRAIT_SRC`, its size `PORTRAIT_PX`. |
| `favicons.py` | Jellyfish-bell favicons and the web manifest. |
| `social_card.py` | The 1200×630 image used when the site is shared. |

`originals/` holds the full-size photos the web images are made from.

## Regenerating the art

The generated files are committed, so the site builds without running any of these.

```
python3 scripts/build_illustrations.py
python3 scripts/favicons.py
python3 scripts/social_card.py
```

Run them in this order after changing `medusa.py` or `build_illustrations.py`. The favicons are drawn from the bell mark that `build_illustrations.py` writes, and the social card is laid out from the jellyfish layers, the stars and the fonts. Each generator is deterministic: re-running one without changing its code gives identical files.

- **Jellyfish.** `medusa.py` writes four layers (back, bell, arms, front), the mark, and a `layers.css` of per-class stroke widths. The widths are kept in `assets/css/site.css`, ahead of the night colours, and `build_illustrations.py` stops if they differ from `layers.css`. It also stops if the drawing's `viewBox` changes, because the tentacle start points in `assets/js/trails.js` (`RIM` and `RIML`) are fractions of that box.
- **Stars.** Hand-drawn asterisks and dot-crosses, from a seeded generator in `build_illustrations.py`. Their positions are in `site.css` (`.sky .s1` to `.s8`, and `.m1` to `.m4` on phones).
- **Grain and specks.** Two tiles written as data URIs to `illustrations.css`. `site.css` sizes and places them.
- **Fonts.** Run `fetch_fonts.py` separately; it needs a network connection. Do it before `social_card.py` if the fonts change.

`trails.js` and the night colours are written by hand, not generated.

## Checks

```
python3 scripts/check_site.py            # builds, then checks _site/; exit status is the number of failures
python3 scripts/check_site.py --external # also requests every outside link
python3 scripts/check_layout.py --shots /tmp/shots   # about two minutes
```

Run both before pushing. Chrome 154 does not exit after writing a screenshot or dumping a DOM, so `check_layout.py` and `social_card.py` start it, wait for the output and then stop it.
