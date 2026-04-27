"""`ctl get <resource> <id>` subcommand."""
from __future__ import annotations

import sys

from .common import (
    DEFAULT_FORMAT,
    EXIT_OK,
    EXIT_USER_ERROR,
    err,
    load_resource_item,
    render,
)

HELP = """\
usage: ctl get <resource> <id> [--format FMT]

Print a single record by id.

Arguments:
  resource          users | orders | tickets | products | sessions
  id                The resource id (e.g. u001, o042).

Options:
  --format FMT      json | yaml | table. Default: table.
  -h, --help        Show this message and exit.

Exit codes:
  0    success
  1    not found / user error
"""


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    if len(argv) < 2:
        err("get requires <resource> and <id>")
        return EXIT_USER_ERROR

    resource = argv[0]
    item_id = argv[1]
    fmt = DEFAULT_FORMAT

    i = 2
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            sys.stdout.write(HELP)
            return EXIT_OK
        if a == "--format":
            if i + 1 >= len(argv):
                err("--format requires a value")
                return EXIT_USER_ERROR
            fmt = argv[i + 1]
            if fmt not in ("json", "yaml", "table"):
                err(f"invalid format: {fmt}")
                return EXIT_USER_ERROR
            i += 2
            continue
        err(f"unknown argument: {a}")
        return EXIT_USER_ERROR

    item = load_resource_item(resource, item_id)
    if item is None:
        err("not found")
        return EXIT_USER_ERROR

    sys.stdout.write(render(item, fmt))
    return EXIT_OK
