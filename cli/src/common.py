"""Shared constants, fixture I/O, state dir, and output formatting for ctl."""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

VERSION = "1.0.0"

# Deterministic "now". All relative date math anchors here so every run
# produces identical output regardless of wall clock.
NOW = datetime(2026, 4, 24, 0, 0, 0, tzinfo=timezone.utc)

DEFAULT_LIMIT = 10
DEFAULT_FORMAT = "table"

RESOURCES = ("users", "orders", "tickets", "products", "sessions")

# Exit codes.
EXIT_OK = 0
EXIT_USER_ERROR = 1     # not found, bad flag, malformed input
EXIT_REFUSED = 2        # pipeline refused / prerequisite unmet


# ---------------------------------------------------------------------------
# Filesystem roots
# ---------------------------------------------------------------------------

def fixtures_dir() -> str:
    """Resolve the fixtures root: $CTL_FIXTURES_DIR, else <repo>/fixtures."""
    env = os.environ.get("CTL_FIXTURES_DIR")
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(here))
    return os.path.join(repo_root, "fixtures")


def state_dir() -> str:
    """Resolve the scratch state dir: $CTL_STATE_DIR, else ~/.ctl-state/."""
    env = os.environ.get("CTL_STATE_DIR")
    if env:
        path = os.path.abspath(env)
    else:
        path = os.path.join(os.path.expanduser("~"), ".ctl-state")
    os.makedirs(path, exist_ok=True)
    return path


def state_path(name: str) -> str:
    return os.path.join(state_dir(), name)


def state_read(name: str) -> Any:
    path = state_path(name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def state_write(name: str, data: Any) -> None:
    path = state_path(name)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def state_delete(name: str) -> bool:
    path = state_path(name)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def state_list() -> list[str]:
    try:
        return sorted(os.listdir(state_dir()))
    except FileNotFoundError:
        return []


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def err(msg: str) -> None:
    """Write a short diagnostic to stderr. No trailing context by design."""
    sys.stderr.write(msg.rstrip("\n") + "\n")


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_resource_list(resource: str) -> list[dict]:
    path = os.path.join(fixtures_dir(), "api", resource, "list.json")
    if not os.path.exists(path):
        err(f"unknown resource: {resource}")
        sys.exit(EXIT_USER_ERROR)
    return load_json(path)


def load_resource_item(resource: str, item_id: str) -> dict | None:
    path = os.path.join(fixtures_dir(), "api", resource, f"{item_id}.json")
    if not os.path.exists(path):
        return None
    return load_json(path)


def resource_of_id(item_id: str) -> str | None:
    """Infer the resource a bare id belongs to by scanning fixtures."""
    for r in RESOURCES:
        if load_resource_item(r, item_id) is not None:
            return r
    return None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

TABLE_MAX_COL = 24  # columns wider than this are truncated with "…"


def _truncate(val: Any) -> str:
    s = "" if val is None else str(val)
    if len(s) > TABLE_MAX_COL:
        # Silent truncation - the gotcha that --format table hides data.
        return s[: TABLE_MAX_COL - 1] + "…"
    return s


def _table(rows: list[dict]) -> str:
    if not rows:
        return "(no rows)\n"
    # Union of keys preserving first-seen order across rows.
    cols: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen:
                cols.append(k)
                seen.add(k)
    widths = {c: len(c) for c in cols}
    cooked: list[list[str]] = []
    for row in rows:
        cooked_row = []
        for c in cols:
            cell = _truncate(row.get(c, ""))
            widths[c] = max(widths[c], len(cell))
            cooked_row.append(cell)
        cooked.append(cooked_row)

    def fmt_row(cells: Iterable[str]) -> str:
        return "  ".join(c.ljust(widths[col]) for c, col in zip(cells, cols))

    header = fmt_row(cols)
    sep = "  ".join("-" * widths[c] for c in cols)
    body = "\n".join(fmt_row(r) for r in cooked)
    return f"{header}\n{sep}\n{body}\n"


def _yaml_scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "" or re.search(r"[:#\n\"']|^\s|\s$|^[-?&*!|>%@`]", s):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _yaml_emit(obj: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return f"{pad}{{}}\n"
        out = []
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{k}:")
                out.append(_yaml_emit(v, indent + 1).rstrip("\n"))
            else:
                rendered = (
                    _yaml_scalar(v)
                    if not isinstance(v, (dict, list))
                    else ("{}" if isinstance(v, dict) else "[]")
                )
                out.append(f"{pad}{k}: {rendered}")
        return "\n".join(out) + "\n"
    if isinstance(obj, list):
        if not obj:
            return f"{pad}[]\n"
        out = []
        for item in obj:
            if isinstance(item, dict):
                keys = list(item.keys())
                if not keys:
                    out.append(f"{pad}- {{}}")
                    continue
                first = keys[0]
                first_val = item[first]
                if isinstance(first_val, (dict, list)) and first_val:
                    out.append(f"{pad}-")
                    out.append(_yaml_emit(item, indent + 1).rstrip("\n"))
                else:
                    out.append(f"{pad}- {first}: {_yaml_scalar(first_val)}")
                    for k in keys[1:]:
                        v = item[k]
                        if isinstance(v, (dict, list)) and v:
                            out.append(f"{pad}  {k}:")
                            out.append(_yaml_emit(v, indent + 2).rstrip("\n"))
                        else:
                            rendered = (
                                _yaml_scalar(v)
                                if not isinstance(v, (dict, list))
                                else ("{}" if isinstance(v, dict) else "[]")
                            )
                            out.append(f"{pad}  {k}: {rendered}")
            else:
                out.append(f"{pad}- {_yaml_scalar(item)}")
        return "\n".join(out) + "\n"
    return f"{pad}{_yaml_scalar(obj)}\n"


def render(data: Any, fmt: str) -> str:
    """Format a dict / list of dicts for stdout according to `fmt`.

    `fmt` must be one of {table, json, yaml}. The caller is responsible for
    validating the flag value before handing it here.
    """
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if fmt == "yaml":
        return _yaml_emit(data)
    if fmt == "table":
        if isinstance(data, list):
            return _table(data)
        if isinstance(data, dict):
            return _table([data])
        return str(data) + "\n"
    raise ValueError(f"unknown format: {fmt}")


# ---------------------------------------------------------------------------
# Date parsing (--since)
# ---------------------------------------------------------------------------

_RELATIVE_RE = re.compile(r"^(\d+)([hd])$")
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})?$"
)


def parse_since(value: str) -> datetime:
    """Parse --since into a UTC datetime.

    Accepts:
      - Relative: '7d', '24h'
      - ISO date: '2026-04-20' (interpreted as start-of-day UTC)
      - ISO datetime: '2026-04-20T12:00:00Z'

    Raises ValueError('invalid date') on anything else. The error message is
    intentionally terse - no format hint.
    """
    if not value:
        raise ValueError("invalid date")
    m = _RELATIVE_RE.match(value)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = timedelta(days=n) if unit == "d" else timedelta(hours=n)
        return NOW - delta
    if _ISO_DATE_RE.match(value):
        try:
            d = datetime.strptime(value, "%Y-%m-%d")
            return d.replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("invalid date")
    if _ISO_DATETIME_RE.match(value):
        try:
            v = value
            if v.endswith("Z"):
                v = v[:-1] + "+00:00"
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            raise ValueError("invalid date")
    raise ValueError("invalid date")


def parse_created_at(s: str) -> datetime:
    """Parse a fixture ISO-8601 timestamp (always with Z suffix)."""
    v = s
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
