"""`ctl search --query Q` subcommand."""
from __future__ import annotations

import json
import sys

from .common import (
    EXIT_OK,
    EXIT_USER_ERROR,
    RESOURCES,
    err,
    load_resource_list,
    state_delete,
    state_read,
)

HELP = """\
usage: ctl search --query Q [--scope RESOURCE] [--i] [--reindex]

Substring search across resource fields. Output is JSON -- a list of
{resource, id, match: {field: value}} objects.

The `--query` value may also be a simple field filter of the form
`field:value` (e.g. `status:paid`). Field filters honour --i.

Options:
  --query Q          Required. Substring, or `field:value`.
  --scope RESOURCE   Restrict to one resource. Default: all.
  --i                Case-insensitive. Default: case-SENSITIVE.
  --reindex          Rebuild the search index (clears the stale flag).
  -h, --help         Show this message and exit.
"""


# ---------------------------------------------------------------------------
# Matching primitives
# ---------------------------------------------------------------------------

def _matches(query: str, haystack: str, insensitive: bool) -> bool:
    if insensitive:
        return query.lower() in haystack.lower()
    return query in haystack


def _facet(query: str) -> tuple[str, str] | None:
    """If `query` looks like `field:value`, return (field, value)."""
    if ":" in query:
        field, _, value = query.partition(":")
        field = field.strip()
        value = value.strip()
        if field and value and " " not in field:
            return field, value
    return None


def _field_value_to_str(v) -> str | None:
    """Render a field value for matching. Returns None for things we
    shouldn't match against (e.g. nested dicts/lists)."""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    return None


def _search_substring(
    resource: str, query: str, insensitive: bool
) -> list[dict]:
    rows = load_resource_list(resource)
    hits: list[dict] = []
    for row in rows:
        matched: dict = {}
        for k, v in row.items():
            # Null-safe: skip None values outright (Anomaly A18 —
            # prevents a crash when searching email fields with NULLs).
            if v is None:
                continue
            if isinstance(v, dict):
                continue
            if isinstance(v, list):
                for item in v:
                    s = _field_value_to_str(item)
                    if s is not None and _matches(query, s, insensitive):
                        matched[k] = v
                        break
                continue
            s = _field_value_to_str(v)
            if s is not None and _matches(query, s, insensitive):
                matched[k] = v
        if matched:
            hits.append({"resource": resource, "id": row.get("id"), "match": matched})
    return hits


def _search_facet(
    resource: str, field: str, value: str, insensitive: bool, stale: bool
) -> list[dict]:
    rows = load_resource_list(resource)
    hits: list[dict] = []

    # Anomaly A6 — when the search index is stale after pipe-07, faceted
    # queries on orders.status don't reflect the live fixtures. We simulate
    # that by hiding the two pipe-07 collateral refunds from a
    # `status:paid` lookup on orders (and reporting them under `status:paid`
    # instead of `status:refunded` for the refunded filter).
    stale_order_ids = {"o088", "o091"}

    for row in rows:
        v = row.get(field)
        s = _field_value_to_str(v)
        if s is None:
            continue

        # Stale-index simulation for orders scope, status field only.
        if stale and resource == "orders" and field == "status":
            if row.get("id") in stale_order_ids:
                # The stale index remembers them as `paid`.
                s = "paid"

        if _matches(value, s, insensitive):
            hits.append({
                "resource": resource,
                "id": row.get("id"),
                "match": {field: s},
            })
    return hits


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    query: str | None = None
    scope: str | None = None
    insensitive = False
    reindex = False

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            sys.stdout.write(HELP)
            return EXIT_OK
        if a == "--query":
            if i + 1 >= len(argv):
                err("--query requires a value")
                return EXIT_USER_ERROR
            query = argv[i + 1]
            i += 2
            continue
        if a == "--scope":
            if i + 1 >= len(argv):
                err("--scope requires a value")
                return EXIT_USER_ERROR
            scope = argv[i + 1]
            if scope not in RESOURCES:
                err(f"invalid scope: {scope}")
                return EXIT_USER_ERROR
            i += 2
            continue
        if a == "--i":
            insensitive = True
            i += 1
            continue
        if a == "--reindex":
            reindex = True
            i += 1
            continue
        err(f"unknown argument: {a}")
        return EXIT_USER_ERROR

    if reindex:
        # Clearing the flag = "index rebuilt". Safe to run with no query.
        state_delete("search_index_stale.json")
        if query is None:
            sys.stdout.write("search index rebuilt\n")
            return EXIT_OK

    if query is None:
        err("--query is required")
        return EXIT_USER_ERROR

    stale = bool(state_read("search_index_stale.json"))

    scopes = (scope,) if scope else RESOURCES
    results: list[dict] = []

    facet = _facet(query)
    for r in scopes:
        if facet is not None:
            field, value = facet
            results.extend(_search_facet(r, field, value, insensitive, stale))
        else:
            results.extend(_search_substring(r, query, insensitive))

    sys.stdout.write(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    return EXIT_OK
