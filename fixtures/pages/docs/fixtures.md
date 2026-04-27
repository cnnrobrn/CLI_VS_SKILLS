# Fixtures

Fixtures live under `fixtures/` (or `$CTL_FIXTURES_DIR` if set). Changing
them changes every command's output. Do not edit fixtures during a
benchmark run. State lives in `~/.ctl-state/` (or `$CTL_STATE_DIR`) and
is safe to `rm -rf` between runs.
