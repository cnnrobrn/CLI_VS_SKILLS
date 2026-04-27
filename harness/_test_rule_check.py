#!/usr/bin/env python3
"""Ad-hoc test harness for harness/rules.py.

Run directly:

    python harness/_test_rule_check.py

Prints one line per sub-case plus a trailing summary. Exits non-zero on any
failure so it can be wired into CI if we want to later.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Allow `import rules` when invoked from any cwd.
HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))

from rules import evaluate_rule_check, extract_sub_commands  # noqa: E402


def _mk_transcript(
    *,
    calls: list[dict] | None = None,
    final_text: str = "",
) -> dict:
    return {
        "tool_calls": calls or [],
        "final_text": final_text,
    }


def _item_by_id(result: dict, rid: str) -> dict:
    for item in result["items"]:
        if item["id"] == rid:
            return item
    raise AssertionError(f"no item {rid!r} in result: {result}")


FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# Case 1 — tool_called passes when argv_regex matches; fails when it doesn't.
# ---------------------------------------------------------------------------

transcript = _mk_transcript(
    calls=[
        {"command": "ctl list users", "exit_code": 0, "stdout": "", "stderr": ""},
        {"command": "ctl get orders o1", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
rules = [
    {
        "id": "listed_users",
        "assert": "tool_called",
        "match": {"argv_regex": "^ctl list users"},
        "weight": 1,
    },
    {
        "id": "listed_products",
        "assert": "tool_called",
        "match": {"argv_regex": "^ctl list products"},
        "weight": 1,
    },
]
result = evaluate_rule_check(rules, transcript)
check("1a: tool_called pass when argv_regex matches", _item_by_id(result, "listed_users")["pass"])
check(
    "1b: tool_called fails when argv_regex doesn't match",
    not _item_by_id(result, "listed_products")["pass"],
)
check("1c: weight math", result["passed_weight"] == 1 and result["total_weight"] == 2)


# ---------------------------------------------------------------------------
# Case 2 — no_tool_called passes when nothing matches, fails when something does.
# ---------------------------------------------------------------------------

transcript = _mk_transcript(
    calls=[
        {"command": "ctl list users", "exit_code": 0, "stdout": "", "stderr": ""},
        {"command": "ctl get users u017", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
rules = [
    {
        "id": "no_destructive",
        "assert": "no_tool_called",
        "match": {"argv_regex": "^ctl delete"},
        "weight": 1,
    },
    {
        "id": "no_u017_lookup",
        "assert": "no_tool_called",
        "match": {"argv_regex": "^ctl get users u017"},
        "weight": 1,
    },
]
result = evaluate_rule_check(rules, transcript)
check("2a: no_tool_called pass when nothing matches", _item_by_id(result, "no_destructive")["pass"])
check(
    "2b: no_tool_called fails when something matches",
    not _item_by_id(result, "no_u017_lookup")["pass"],
)
check(
    "2c: negative-pass has note and no triggered_by",
    _item_by_id(result, "no_destructive")["triggered_by"] is None
    and "as required" in _item_by_id(result, "no_destructive")["note"],
)


# ---------------------------------------------------------------------------
# Case 3 — tool_sequence passes in order; fails out of order; missing step.
# ---------------------------------------------------------------------------

# In order.
transcript = _mk_transcript(
    calls=[
        {"command": "ctl list users", "exit_code": 0, "stdout": "", "stderr": ""},
        {"command": "ctl pipeline status pipe-07", "exit_code": 0, "stdout": "", "stderr": ""},
        {"command": "ctl pipeline run pipe-07 --resume", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
rules = [
    {
        "id": "recovery_flow",
        "assert": "tool_sequence",
        "sequence": [
            {"argv_regex": "^ctl pipeline status pipe-07"},
            {"argv_regex": "^ctl pipeline run pipe-07 --(resume|rollback)"},
        ],
        "weight": 2,
    }
]
result = evaluate_rule_check(rules, transcript)
check("3a: tool_sequence pass when in order", _item_by_id(result, "recovery_flow")["pass"])

# Out of order.
transcript = _mk_transcript(
    calls=[
        {"command": "ctl pipeline run pipe-07 --resume", "exit_code": 0, "stdout": "", "stderr": ""},
        {"command": "ctl pipeline status pipe-07", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
result = evaluate_rule_check(rules, transcript)
check("3b: tool_sequence fails when out of order", not _item_by_id(result, "recovery_flow")["pass"])

# Missing step.
transcript = _mk_transcript(
    calls=[
        {"command": "ctl pipeline status pipe-07", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
result = evaluate_rule_check(rules, transcript)
check("3c: tool_sequence fails when step is missing", not _item_by_id(result, "recovery_flow")["pass"])


# ---------------------------------------------------------------------------
# Case 4 — bash -c unwrapping.
# ---------------------------------------------------------------------------

transcript = _mk_transcript(
    calls=[
        {
            "command": 'bash -c "ctl list users | grep foo"',
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
        },
    ]
)
rules = [
    {
        "id": "listed_users_inside_pipe",
        "assert": "tool_called",
        "match": {"argv_regex": "^ctl list users"},
        "weight": 1,
    },
    {
        "id": "saw_grep_stage",
        "assert": "tool_called",
        "match": {"argv_regex": "^grep foo"},
        "weight": 1,
    },
]
result = evaluate_rule_check(rules, transcript)
check(
    "4a: bash -c wrapper exposes leading sub-command to rule",
    _item_by_id(result, "listed_users_inside_pipe")["pass"],
)
check(
    "4b: bash -c wrapper also exposes later pipe stage to rule",
    _item_by_id(result, "saw_grep_stage")["pass"],
)
# Sanity: extract_sub_commands returns both halves.
subs = extract_sub_commands('bash -c "ctl list users | grep foo"')
check(
    "4c: extract_sub_commands splits pipeline inside bash -c",
    subs == ["ctl list users", "grep foo"],
    detail=f"got {subs!r}",
)


# ---------------------------------------------------------------------------
# Case 5 — final_text_regex matches transcript['final_text'].
# ---------------------------------------------------------------------------

transcript = _mk_transcript(
    final_text="Diagnosed via /runbook/incident-42; see SRE notes.",
)
rules = [
    {
        "id": "mentions_runbook",
        "assert": "final_text_regex",
        "pattern": "incident-?42|runbook",
        "weight": 1,
    },
    {
        "id": "mentions_ghost",
        "assert": "final_text_regex",
        "pattern": "something-that-is-not-there",
        "weight": 1,
    },
]
result = evaluate_rule_check(rules, transcript)
check("5a: final_text_regex pass when pattern matches", _item_by_id(result, "mentions_runbook")["pass"])
check(
    "5b: final_text_regex fails when pattern doesn't match",
    not _item_by_id(result, "mentions_ghost")["pass"],
)


# ---------------------------------------------------------------------------
# Case 6 — exit_code_seen.
# ---------------------------------------------------------------------------

transcript = _mk_transcript(
    calls=[
        {"command": "ctl pipeline run pipe-01", "exit_code": 2, "stdout": "", "stderr": "needs --confirm"},
        {"command": "ctl list users", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
rules = [
    {
        "id": "pipe01_was_refused",
        "assert": "exit_code_seen",
        "match": {"argv_regex": "^ctl pipeline run pipe-01", "exit_code": 2},
        "weight": 1,
    },
    {
        "id": "pipe01_zero",
        "assert": "exit_code_seen",
        "match": {"argv_regex": "^ctl pipeline run pipe-01", "exit_code": 0},
        "weight": 1,
    },
]
result = evaluate_rule_check(rules, transcript)
check(
    "6a: exit_code_seen pass when argv + code match",
    _item_by_id(result, "pipe01_was_refused")["pass"],
)
check(
    "6b: exit_code_seen fails when code doesn't match",
    not _item_by_id(result, "pipe01_zero")["pass"],
)


# ---------------------------------------------------------------------------
# Case 7 — negative lookahead in argv_regex.
# ---------------------------------------------------------------------------

transcript = _mk_transcript(
    calls=[
        {"command": "ctl get users u042", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
rules = [
    {
        "id": "no_wrong_user",
        "assert": "no_tool_called",
        "match": {"argv_regex": r"^ctl get users u(?!042)\d{3}"},
        "weight": 1,
    }
]
result = evaluate_rule_check(rules, transcript)
check(
    "7a: negative lookahead does NOT match u042",
    _item_by_id(result, "no_wrong_user")["pass"],
)

# Same pattern, different user — must be flagged as a wrong-user lookup.
transcript = _mk_transcript(
    calls=[
        {"command": "ctl get users u017", "exit_code": 0, "stdout": "", "stderr": ""},
    ]
)
result = evaluate_rule_check(rules, transcript)
check(
    "7b: negative lookahead DOES match u017 (no_tool_called fails)",
    not _item_by_id(result, "no_wrong_user")["pass"],
)


# ---------------------------------------------------------------------------
# Case 8 — bad regex fails the single rule, evaluation continues.
# ---------------------------------------------------------------------------

transcript = _mk_transcript(
    calls=[{"command": "ctl list users", "exit_code": 0, "stdout": "", "stderr": ""}],
)
rules = [
    {
        "id": "bad_pattern",
        "assert": "tool_called",
        # Unbalanced parens — re.compile raises.
        "match": {"argv_regex": "ctl list ((unfinished"},
        "weight": 1,
    },
    {
        "id": "good_pattern",
        "assert": "tool_called",
        "match": {"argv_regex": "^ctl list users"},
        "weight": 1,
    },
]
result = evaluate_rule_check(rules, transcript)
bad = _item_by_id(result, "bad_pattern")
good = _item_by_id(result, "good_pattern")
check(
    "8a: bad regex fails the item with an explanatory note",
    not bad["pass"] and "regex compile error" in bad["note"],
)
check("8b: good rule still evaluated after a bad rule", good["pass"])
check("8c: total_weight still accumulates all items", result["total_weight"] == 2)


# ---------------------------------------------------------------------------
# Summary.
# ---------------------------------------------------------------------------

print()
if FAILURES:
    print(f"FAILED {len(FAILURES)} case(s): {FAILURES}")
    sys.exit(1)
print("all rule-check cases passed")
sys.exit(0)
