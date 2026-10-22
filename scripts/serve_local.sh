#!/usr/bin/env bash
# Preview the site at http://localhost:4000, rebuilding when a file changes. Stop it with Ctrl-C.
#
#   scripts/serve_local.sh             # extra arguments go to `jekyll serve`, e.g. --port 4001
#
# Uses the same gems as scripts/build_local.sh (see scripts/gems.sh): the repo Gemfile on Ruby 3
# or later, scripts/dev/Gemfile (installed by scripts/dev/install.sh) on an older Ruby.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/scripts/gems.sh"
if [ "${BUNDLE_GEMFILE:-}" = "$ROOT/scripts/dev/Gemfile" ] && [ ! -d "$BUNDLE_PATH" ]; then
  echo "This Ruby ($(ruby -e 'print RUBY_VERSION')) builds with scripts/dev/Gemfile; install its gems first:" >&2
  echo "  scripts/dev/install.sh" >&2
  exit 1
fi
export PAGES_REPO_NWO="${PAGES_REPO_NWO:-hannapalya/hannapalya.github.io}"
cd "$ROOT"
exec bundle exec jekyll serve --source "$ROOT" --host 127.0.0.1 --port 4000 "$@"
