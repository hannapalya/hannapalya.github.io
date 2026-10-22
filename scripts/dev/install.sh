#!/usr/bin/env bash
# Install the gems in scripts/dev/Gemfile (github-pages 231, pinned for Ruby 2.6) into vendor/dev/
# in the repo. Needs a network connection and takes a few minutes; nothing needs sudo.
#
#   scripts/dev/install.sh
#
# Then scripts/build_local.sh, scripts/serve_local.sh and scripts/check_site.py use these gems
# whenever Ruby is older than 3. Delete vendor/dev/ to start again.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GEMS=dev
. "$ROOT/scripts/gems.sh"
cd "$ROOT"
bundle install
echo "Installed into ${BUNDLE_PATH#"$ROOT"/}. Build with scripts/build_local.sh, preview with scripts/serve_local.sh."
