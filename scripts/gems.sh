# Sourced (not run) by build_local.sh, serve_local.sh and dev/install.sh, with ROOT set to the repo.
# Picks the gems Jekyll runs with:
#   - JEKYLL_ENV_DIR set: the Gemfile and the vendor/ install in that folder;
#   - GEMS=dev, or a Ruby older than 3 (macOS's built-in Ruby 2.6): scripts/dev/Gemfile, installed
#     into vendor/dev/ in the repo by scripts/dev/install.sh;
#   - otherwise (Ruby 3 or later): the repo Gemfile, installed with `bundle install`.
if [ -n "${JEKYLL_ENV_DIR:-}" ]; then
  export BUNDLE_GEMFILE="$JEKYLL_ENV_DIR/Gemfile"
  export BUNDLE_PATH="$JEKYLL_ENV_DIR/vendor/bundle"
  export GEM_HOME="$JEKYLL_ENV_DIR/vendor/gems"
elif [ "${GEMS:-}" = dev ] || ! ruby -e 'exit RUBY_VERSION.to_i >= 3'; then
  export BUNDLE_GEMFILE="$ROOT/scripts/dev/Gemfile"
  export BUNDLE_PATH="$ROOT/vendor/dev/bundle"
  export GEM_HOME="$ROOT/vendor/dev/gems"   # so nothing is written to the system's gem folder
fi
