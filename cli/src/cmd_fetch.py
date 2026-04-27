"""`ctl fetch <url-or-slug>` subcommand."""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from .common import (
    EXIT_OK,
    EXIT_USER_ERROR,
    err,
    fixtures_dir,
    state_read,
)

# Anomaly A7 — /docs/auth returns a canned 404 by default. `ctl cache clear`
# flips a sentinel that lets the real page through. The state flag is the
# POSITIVE form (`auth_cache_ok.json`) so that a freshly-wiped state dir
# yields the default (broken) behaviour.
_AUTH_OK_FLAG = "auth_cache_ok.json"

HELP = """\
usage: ctl fetch <url-or-slug>

Print the markdown page for the given slug. Accepts either a bare slug
(/docs/getting-started) or a full URL whose path is a known slug
(https://example.com/docs/getting-started).

Exit codes:
  0    success (including the canned 404 body)
  1    page not found
"""

# Paths that are affected by the "pages cache stale" flag. After pipe-03
# runs, any fetch under /docs/* returns the canned 404 page until
# `ctl cache clear` is run. (Anomaly A4.)
_STALE_PREFIXES = ("/docs/",)

# Pages that are ALWAYS stale until cache clear, regardless of pipe-03.
# (Anomaly A7.)
_ALWAYS_STALE = ("/docs/auth",)


def _normalize_slug(target: str) -> str:
    s = target.strip()
    if s.startswith(("http://", "https://")):
        s = urlparse(s).path or "/"
    if not s.startswith("/"):
        s = "/" + s
    return s


def _slug_to_path(slug: str) -> str:
    rel = slug.lstrip("/") + ".md"
    return os.path.join(fixtures_dir(), "pages", rel)


def _stale_404_body() -> str:
    path = os.path.join(fixtures_dir(), "pages", "_stale_404.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    # Fallback (should never happen when fixtures are properly generated).
    return (
        "# 404 Not Found\n\n"
        "This page is unavailable because the local page cache is stale.\n"
        "Run `ctl cache clear` and try again.\n"
    )


def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    slug = _normalize_slug(argv[0])

    # Anomaly A7 — /docs/auth serves the canned 404 body by default.
    # Running `ctl cache clear` writes the `auth_cache_ok` sentinel, which
    # lets the real page through.
    if slug in _ALWAYS_STALE:
        if state_read(_AUTH_OK_FLAG) is None:
            sys.stdout.write(_stale_404_body())
            return EXIT_OK
        # Fall through to the normal file lookup.

    # Anomaly A4 — if the global cache_stale flag is set (pipe-03 ran) and
    # the slug is under /docs/, return the 404 body until cleared.
    if state_read("cache_stale.json") and any(slug.startswith(p) for p in _STALE_PREFIXES):
        sys.stdout.write(_stale_404_body())
        return EXIT_OK

    path = _slug_to_path(slug)
    if not os.path.exists(path):
        err("not found")
        return EXIT_USER_ERROR
    with open(path, "r", encoding="utf-8") as f:
        sys.stdout.write(f.read())
    return EXIT_OK
