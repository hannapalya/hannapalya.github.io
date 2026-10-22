#!/usr/bin/env bash
# Build the site with the gem set GitHub Pages uses (the github-pages gem).
#
#   scripts/build_local.sh            # builds into _site/
#   scripts/build_local.sh /tmp/out   # builds into /tmp/out
#
# On Ruby 3 or later it uses the repo Gemfile (after `bundle install`). On an older Ruby, such as
# macOS's built-in 2.6, it uses scripts/dev/Gemfile, installed by scripts/dev/install.sh. If
# JEKYLL_ENV_DIR is set, it uses the Gemfile and vendor/ install in that folder instead
# (see scripts/gems.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT/_site}"
. "$ROOT/scripts/gems.sh"
if [ "${BUNDLE_GEMFILE:-}" = "$ROOT/scripts/dev/Gemfile" ] && [ ! -d "$BUNDLE_PATH" ]; then
  echo "This Ruby ($(ruby -e 'print RUBY_VERSION')) builds with scripts/dev/Gemfile; install its gems first:" >&2
  echo "  scripts/dev/install.sh" >&2
  exit 1
fi
export PAGES_REPO_NWO="${PAGES_REPO_NWO:-hannapalya/hannapalya.github.io}"
cd "$ROOT"
JEKYLL_ENV=production exec bundle exec jekyll build --source "$ROOT" --destination "$DEST" --strict_front_matter
