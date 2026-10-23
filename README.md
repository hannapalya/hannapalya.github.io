# hannapalya.com

Personal site of Hanna Pálya, built with Jekyll and served by GitHub Pages from `main`.

## Updating content

- **Intro:** edit `index.md`. It is two short paragraphs under the name: what you do now, then what you did before. If it changes your role, employer or city, see the table below. `check_site.py` also checks that the intro still says each phrase in its `MUST_SAY` list and links each name in its `INTRO_LINKS` list (Fourth Eon Biosecurity and the Centre for Long-Term Resilience), so change those lists when you rewrite the intro.
- **Writing (publications):** add an entry at the top of `_data/publications.yml` with `title`, `authors`, `venue`, `year` and `url`. The home page shows the title, linked to `url` (the DOI, or for a post its address), then the year in brackets, and nothing else: there are no summaries, so do not add a `summary`. List only published work.
- **Other projects:** the line under "writing" on the home page, in the section labelled "other projects" (`id="projects"`). To add a project, add an entry to `_data/other_projects.yml` with a `label` (the link's text, a word or two) and a `url`. The links show on one line, in the file's order, separated by "·", with no descriptions. `check_site.py` expects exactly these links, so add the new one to its `OTHER_PROJECTS` list too. There is no projects page: `/projects/` (`projects.md`) redirects to this section.
- **Stars that lead somewhere:** edit `_data/stars.yml`. Each entry, a `label` and a `url`, turns one of the stars in the sky on the home page into a secret link: it looks like the other stars until you hover over it or tab to it, when it brightens and shows its label. There are at most five, in priority order; the comment at the top of the file says which show at which screen widths.
- **The jellyfish link:** `jellyfish:` in `_config.yml`, a `label` and a `url` (now "moon jelly" and the moon jelly's Wikipedia page). The jellyfish's bell, on the home page and the 404 page, is a secret link like the stars: it looks the same until you hover over it or tab to it, when its glow brightens and the label shows beside it. Only the bell and the oral arms under it are the link, not the tentacles. Keep the label short, and restart `scripts/serve_local.sh` after editing `_config.yml`.
- **Contact links:** see the table below.
- **A blog post:** add `_posts/YYYY-MM-DD-title.md` with front matter `title:`. It is listed on the Writing page, `/blog/`, and the feed is linked, once there is at least one post. The home page does not link to the Writing page. With the first post, also delete the `sitemap: false` line from `blog.html`, so the Writing page goes into the sitemap (`check_site.py` reminds you). Give an image in a post its size, so the page does not jump as it loads: `![What the image shows](/assets/img/posts/name.webp){: width="800" height="600"}`.
- **Photo:** the page shows no photo. `assets/img/hanna.jpg` is only the `image` in the home page's JSON-LD. To change it, put the original in `scripts/originals/`, point `PORTRAIT_SRC` in `scripts/make_images.py` at it, add its crop to `PORTRAIT_CROPS` if the face is not in the middle, and run the script. It writes a `PORTRAIT_PX` (288px) square.
- **Crochet photos:** put the original in `scripts/originals/`, add a line to `CROCHET` in `scripts/make_images.py` (file, caption, alt text), and run it. It writes the web image and `_data/crochet.yml`. The gallery is at `/crochet/`; the home page does not link to it.

`python3 scripts/check_site.py` checks the content against these files, so it keeps passing when you edit them as above. It fails when an entry is missing a field the page shows (a publication's link or year) or has a `summary`, and when the places that repeat a fact disagree.

### If your job, city or links change

These facts are written in more than one place, so change every one in the row. `check_site.py` fails while the tagline, the JSON-LD and the intro disagree, or the two lists of links do.

| Fact | Where it is written |
| --- | --- |
| Role and employer | `index.md` (the intro). `_config.yml`: `tagline:` (the home page's title in search results and browser tabs, and the share image) and `description:` (the summary search engines and link previews show; `check_site.py` expects its exact words in `DESCRIPTION`, so change that too). `_includes/person.json-ld.html`: `jobTitle`, and `worksFor` with the employer's name and website. Then run `python3 scripts/social_card.py` to redraw the share image, which takes the role from `tagline:`. |
| City | `index.md` (the intro) and `homeLocation` in `_includes/person.json-ld.html`. |
| Email | `email:` in `_config.yml`. It is used for the link under the intro and in the JSON-LD. |
| Profile links (Google Scholar, GitHub, LinkedIn, X) | `_config.yml`: `links:` (the line under the intro) and the same addresses again under `social.links:` (the JSON-LD `sameAs`). For X, also `twitter.username` and `author.twitter`. For Google Scholar, also `redirect_to:` in `papers.md` (/papers/ sends visitors there). To add or remove a profile, also edit the links line in `_layouts/home.html`, which names each one. |
| Name | `title:`, `author.name` and `social.name` in `_config.yml`, then run `python3 scripts/social_card.py`. |
| Degree or university | `alumniOf` in `_includes/person.json-ld.html`. The pages themselves claim no degree, and `check_site.py` fails if one does. |

The favicons are a sparkle, with no text, so a change of job, city or links does not touch them. Run `python3 scripts/favicons.py` only after changing the colours `--star` and `--paper` (see "Regenerating the art").

## Previewing locally

The site builds with the `github-pages` gem, the same gems GitHub Pages uses. There are two ways to install them.

**With Ruby 3 or later** (for example `brew install ruby`, or rbenv):

```
bundle install
bundle exec jekyll serve
```

To keep the gems inside the repo instead of in Ruby's own folder, run `bundle config set --local path vendor/bundle` before `bundle install`.

**With the Ruby that comes with macOS** (2.6, which the current `github-pages` gems no longer support; no Homebrew or admin rights needed):

```
scripts/dev/install.sh     # once: installs the pinned gems in scripts/dev/Gemfile into vendor/dev/ (a few minutes)
scripts/serve_local.sh     # preview, rebuilding as files change; Ctrl-C stops it
```

Either way, open http://localhost:4000. If another program already uses port 4000, run `scripts/serve_local.sh --port 4001` (or `bundle exec jekyll serve --port 4001`) and open that port instead. `scripts/build_local.sh` builds the site once into `_site/`. Both scripts choose the gems by the Ruby they find: the repo `Gemfile` on Ruby 3 or later, `scripts/dev/Gemfile` on an older Ruby. `vendor/` is ignored by git and left out of the site.

Before pushing, run `python3 scripts/check_site.py` (it builds the site the same way) and `python3 scripts/check_layout.py`. The checks need Python 3 and Google Chrome; the art scripts and `--shots` also need `python3 -m pip install --user pillow numpy`. The checks are described in `scripts/README.md`.

## How the site looks

The site has one look, a night sky with a large moon jellyfish in it. There is no light theme, no theme toggle and no script that sets a theme before the page paints. The stylesheet declares `color-scheme: dark`, and the page's `theme-color` is the night background.

The home page opens with the name, the intro and, under it, the contact links on one line. The jellyfish's tentacles run down the margin beside the text. From the right half of the bell come a loose bunch of up to three and one more strand of its own a little further in, wherever it still clears the text (not on phones). From the left half come up to three more, each in a lane of its own between the text and those strands, as many as fit; where two or more fit, the outermost ends partway down. A left-hand strand that finds no lane (on medium screens and phones) hangs from the rim and fades out above the first text or rule below it, so on phones they end before the name. Each section rule is one of the right-hand strands peeling off in a curl. Past the last rule the long strands run on, thinning out and fading to nothing over their last 12rem, and end a little above the foot of the page. There is no footer: the page ends after the "other projects" section, with sky below it.

The jellyfish is moonlight: moon-white lines with a soft glow, four pearl-white gonads that glow a little more, and a faint halo in the sky behind its bell. The halo is part of the page background (`--halo` in `site.css`) and follows the jellyfish at each breakpoint; pages without the jellyfish in the sky have none. There is no red anywhere, and the links, tentacles and section rules share the moonlight.

### What draws it

| Part | Where it lives |
| --- | --- |
| Stylesheet | `assets/css/site.css`, the only stylesheet besides the generated `assets/css/fonts.css`. Colours are tokens on `:root` (`--paper`, `--sky-*`, `--ink`, `--muted`, `--jelly*`, `--glow`, `--link*`, `--halo`). |
| Jellyfish | Four stacked SVG layers (back, bell, arms, front) in `_includes/illustrations/jelly-*.svg`, assembled by `_includes/jellyfish.html`. The bell layer holds the gonads in their own group, which the stylesheet colours pearl white (`--jelly-gonad`, `--jelly-gonad-fill`) and gives its own glow. The link on the bell is `_includes/jelly-link.html`, laid over the drawing (it shares the plate's place in `site.css`). |
| Stars | `_includes/illustrations/sky.html`: hand-drawn six-ray asterisks and dot-crosses, with a speckle tile behind them. The set changes at narrow widths. The secret links from `_data/stars.yml` are `_includes/star-links.html`, placed over up to five of the stars. |
| Grain | A noise tile laid over the whole page by `body::before`. Its image is in `_includes/illustrations/illustrations.css`, which `_includes/head.html` inlines. |
| Trails | `assets/js/trails.js` measures the page and draws every tentacle and section rule into one SVG overlay (`svg.trails`) under the text. |
| Icon | `assets/favicon/` and `/favicon.ico`: a four-pointed sparkle with a small one at its upper right (`SPARKLES` in `scripts/favicons.py`), in the star white on the night background. The small icons are fitted to whole pixels so they stay crisp at 16px, and the home-screen icons (180px and up) have a faint glow. |

The sky, the jellyfish and the script belong to the home page, which has no header bar: the name is its heading. Without JavaScript the section rules are plain CSS hairlines (`border-top` on `.sec`). With it, `trails.js` hides those and draws each rule, as a curl where a tentacle can reach it and as a straight line where none can. Under `prefers-reduced-motion` everything appears without the draw-in animation. Subpages (Crochet, Writing, posts and the 404 page) share the night colours and the type, and have a small "Hanna Pálya" link to the home page at the top left. The 404 page shows the jellyfish; none of them loads a script.

### Fonts

The site uses one typeface, Quicksand, chosen because its thin, round-ended strokes match the hand-drawn stars. The name is set at weight 300 and display size. Everything else is weight 400 at one text size; section labels are lowercase words in the muted colour. In the sections, each entry is in the text colour, a writing entry being just its linked title and the year in brackets; only the labels and the · separators are muted. There are no small caps, italics or monospaced labels.

Quicksand is a variable font (weights 300 to 700), self-hosted in `assets/fonts/` (latin and latin-ext subsets only) under the SIL Open Font License 1.1, and declared in `assets/css/fonts.css`. Nothing loads from Google at run time. To update it, run `python3 scripts/fetch_fonts.py` (it needs a network connection) and commit the result.

## Regenerating the art

The jellyfish, stars and textures are generated, and the outputs are committed. Every generator is deterministic, so re-running one gives identical files unless its code or numbers have changed.

```
python3 scripts/build_illustrations.py   # jellyfish layers, stars, grain and speck tiles
python3 scripts/favicons.py              # the sparkle favicons and web manifest
python3 scripts/social_card.py           # the 1200×630 share image (needs Google Chrome)
```

The share image also shows your name and role (`title` and `tagline` in `_config.yml`), so run `social_card.py` again after changing either.

Run them in that order after changing `scripts/medusa.py` or anything in `scripts/build_illustrations.py`. The scripts need Python 3 with `numpy` (for `medusa.py`) and `Pillow`. `build_illustrations.py` stops with a message if the jellyfish's stroke widths in `assets/css/site.css` have drifted from the ones `medusa.py` writes, or if the drawing's `viewBox` changed, because the trail start points in `trails.js` assume it. The stylesheet's night colours and `trails.js` are not generated, so edit them by hand.

See `scripts/README.md` for what each script does.
