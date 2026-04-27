"""`ctl cache status` and `ctl cache clear [<scope>]`."""
from __future__ import annotations

import sys

from .common import (
    EXIT_OK,
    EXIT_USER_ERROR,
    err,
    state_delete,
    state_list,
    state_read,
    state_write,
)

HELP = """\
usage: ctl cache status
       ctl cache clear [<scope>]

`status` prints the current state/cache flags.
`clear`  wipes the state directory (or a single scope by name).

Scopes recognised by `clear`:
  pages            Reset the page cache (clears stale-after-pipe-03 and the
                   /docs/auth 404 anomaly).
  search           Reset the search-index-stale flag.
  pipelines        Reset recorded pipeline run state.
  all              (default) Clear everything.

Options:
  -h, --help       Show this message.
"""

# State files owned by each scope. cache clear <scope> removes just those.
SCOPES: dict[str, list[str]] = {
    "pages": ["cache_stale.json"],
    "search": ["search_index_stale.json"],
    "pipelines": [
        "pipe-03_ran.json",
        "pipe-07_state.json",
    ],
}


def _status() -> str:
    pages_stale = state_read("cache_stale.json")
    search_stale = state_read("search_index_stale.json")
    pipe_03_ran = state_read("pipe-03_ran.json") is not None
    pipe_07 = state_read("pipe-07_state.json")
    auth_ok = state_read("auth_cache_ok.json") is not None

    files = state_list()

    lines = [
        f"pages_cache_stale: {'yes' if pages_stale else 'no'}",
        f"auth_page_ok: {'yes' if auth_ok else 'no'}",
        f"search_index_stale: {'yes' if search_stale else 'no'}",
        f"pipe-03_ran_in_session: {'yes' if pipe_03_ran else 'no'}",
        f"pipe-07_state: {pipe_07.get('state') if pipe_07 else 'clean'}",
        f"state_files: {', '.join(files) if files else '(none)'}",
    ]
    return "\n".join(lines) + "\n"


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    sub = argv[0]
    rest = argv[1:]

    if sub in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    if sub == "status":
        sys.stdout.write(_status())
        return EXIT_OK

    if sub == "clear":
        # Default scope is 'all'.
        scope = rest[0] if rest else "all"
        if scope in ("-h", "--help"):
            sys.stdout.write(HELP)
            return EXIT_OK

        if scope == "all":
            names: list[str] = []
            for s in SCOPES.values():
                names.extend(s)
            # Also clear any other state files that might exist.
            for f in state_list():
                if f not in names:
                    names.append(f)
        elif scope in SCOPES:
            names = SCOPES[scope]
        else:
            err(f"unknown cache scope: {scope}")
            return EXIT_USER_ERROR

        removed = 0
        for n in names:
            if state_delete(n):
                removed += 1

        # Clearing the `pages` or `all` scope also repairs the persistent
        # /docs/auth 404 — it writes the positive sentinel so subsequent
        # fetches serve the real page.
        if scope in ("pages", "all"):
            state_write("auth_cache_ok.json", {"cleared": True})

        sys.stdout.write(f"cleared {removed} state entr{'y' if removed == 1 else 'ies'} ({scope})\n")
        return EXIT_OK

    err(f"unknown cache subcommand: {sub}")
    return EXIT_USER_ERROR
