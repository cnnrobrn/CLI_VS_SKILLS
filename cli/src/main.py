"""Top-level dispatcher for `ctl`."""
from __future__ import annotations

import sys

from . import (
    cmd_cache,
    cmd_diff,
    cmd_fetch,
    cmd_get,
    cmd_list,
    cmd_pipeline,
    cmd_search,
)
from .common import EXIT_OK, EXIT_USER_ERROR, VERSION, err

TOP_HELP = """\
ctl - deterministic fixture-backed CLI.

usage: ctl <command> [args...]

Commands:
  list <resource>           List records for a resource.
  get <resource> <id>       Fetch a single record.
  fetch <url-or-slug>       Print a fixture markdown page.
  search --query Q          Substring search across resources.
  diff <a> <b>              Structured JSON diff of two records.
  pipeline run <name>       Run a named pipeline.
  pipeline status <name>    Show last recorded state for a pipeline.
  cache status              Show cache / state flags.
  cache clear [<scope>]     Clear cached state.
  version                   Print version and exit.

Global options:
  -h, --help                Show this help (or per-command help).

Resources: users, orders, tickets, products, sessions.
Formats:   json, yaml, table (default table).

Exit codes:
  0   success
  1   user error (not found, bad flag, invalid input)
  2   refused / prerequisite-unmet

Run `ctl <command> --help` for per-command options.
"""


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(TOP_HELP)
        return EXIT_OK

    cmd = argv[0]
    rest = argv[1:]

    if cmd == "version":
        sys.stdout.write(f"ctl {VERSION}\n")
        return EXIT_OK
    if cmd == "list":
        return cmd_list.run(rest)
    if cmd == "get":
        return cmd_get.run(rest)
    if cmd == "fetch":
        return cmd_fetch.run(rest)
    if cmd == "pipeline":
        return cmd_pipeline.run(rest)
    if cmd == "diff":
        return cmd_diff.run(rest)
    if cmd == "search":
        return cmd_search.run(rest)
    if cmd == "cache":
        return cmd_cache.run(rest)

    err(f"unknown command: {cmd}")
    return EXIT_USER_ERROR
