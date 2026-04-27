"""`ctl list <resource>` subcommand."""
from __future__ import annotations

import sys

from .common import (
    DEFAULT_FORMAT,
    DEFAULT_LIMIT,
    EXIT_OK,
    EXIT_USER_ERROR,
    err,
    load_resource_list,
    parse_created_at,
    parse_since,
    render,
)

HELP = """\
usage: ctl list <resource> [--status STATUS] [--since DATE]
                           [--limit N] [--format FMT]

Print a page of records for a resource.

Arguments:
  resource          users | orders | tickets | products | sessions

Options:
  --status STATUS   Filter rows by exact match on the `status` field.
  --since DATE      Only rows with created_at >= DATE. Accepts ISO
                    (2026-04-20 / 2026-04-20T12:00:00Z) or relative
                    (7d, 24h).
  --limit N         Maximum rows to return. Default: 10.
  --format FMT      json | yaml | table. Default: table.
  -h, --help        Show this message and exit.
"""


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    resource = argv[0]
    status: str | None = None
    since: str | None = None
    limit = DEFAULT_LIMIT
    fmt = DEFAULT_FORMAT

    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            sys.stdout.write(HELP)
            return EXIT_OK
        if a == "--status":
            if i + 1 >= len(argv):
                err("--status requires a value")
                return EXIT_USER_ERROR
            status = argv[i + 1]
            i += 2
            continue
        if a == "--since":
            if i + 1 >= len(argv):
                err("--since requires a value")
                return EXIT_USER_ERROR
            since = argv[i + 1]
            i += 2
            continue
        if a == "--limit":
            if i + 1 >= len(argv):
                err("--limit requires a value")
                return EXIT_USER_ERROR
            try:
                limit = int(argv[i + 1])
            except ValueError:
                err("--limit must be an integer")
                return EXIT_USER_ERROR
            i += 2
            continue
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

    rows = load_resource_list(resource)

    if status is not None:
        rows = [r for r in rows if r.get("status") == status]

    if since is not None:
        try:
            since_dt = parse_since(since)
        except ValueError:
            err("invalid date")
            return EXIT_USER_ERROR
        filtered = []
        for r in rows:
            ts = r.get("created_at") or r.get("started_at")
            if ts is None:
                continue
            try:
                if parse_created_at(ts) >= since_dt:
                    filtered.append(r)
            except ValueError:
                continue
        rows = filtered

    if limit >= 0:
        rows = rows[:limit]

    sys.stdout.write(render(rows, fmt))
    return EXIT_OK
