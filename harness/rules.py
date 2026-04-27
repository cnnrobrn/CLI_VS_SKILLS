#!/usr/bin/env python3
"""Rule-based scoring for CLI_VS_SKILLS transcripts.

Given a task's ``rule_check`` block and a transcript (as produced by
``run.py``), decide pass/fail for each rule item without calling an LLM.

Assertion vocabulary (exact):

    tool_called        — at least one tool call matches ``match``.
    no_tool_called     — zero tool calls match ``match``.
    tool_sequence      — each element of ``sequence`` matches at least one
                         tool call, and they occur in that order (not
                         necessarily contiguously).
    final_text_regex   — agent's ``final_text`` matches ``pattern``.
    final_text_contains — agent's ``final_text`` contains ``text``.
    exit_code_seen     — at least one tool call matches ``match`` AND its
                         exit code equals ``match.exit_code``.

Predicate fields under ``match`` / inside ``sequence`` entries (all optional;
all specified fields must match — AND semantics):

    argv_prefix    : list[str]   — argv tokens start with this prefix.
    argv_regex     : str         — regex on the joined argv string (after
                                    ``bash -c`` unwrapping; see below).
    stdout_regex   : str         — regex on tool call stdout.
    stderr_regex   : str         — regex on tool call stderr.
    exit_code      : int         — tool call exit code equals this value.

``bash -c`` unwrapping: agents often run ``bash -c "ctl list orders | grep
foo"``. For predicate matching, if a tool call's argv is ``["bash", "-c",
"<inner>"]`` we evaluate the predicate against the list of sub-commands
obtained by splitting ``<inner>`` on ``;``, ``&&``, ``||``, ``|`` (same
splitter ``run.py`` uses for the allowlist). A rule matches the call if
*any* sub-command satisfies the predicate.

Public surface:

    evaluate_rule_check(rule_items, transcript) -> dict
"""

from __future__ import annotations

import re
import shlex
from typing import Any

# Re-use the exact splitter the allowlist uses so our "what command did the
# agent run" view matches the harness's view. Pulled lazily to avoid a hard
# import cycle if rules.py is used standalone in tests.
try:
    from run import _split_sequence  # type: ignore
except ImportError:  # pragma: no cover — fallback for isolated test harness
    _split_sequence = None  # type: ignore


# ---------------------------------------------------------------------------
# Sub-command extraction
# ---------------------------------------------------------------------------


_FALLBACK_SEQUENCE_OPS = [";", "&&", "||", "|"]


def _fallback_split_sequence(cmd: str) -> list[str]:
    """Fallback splitter matching run._split_sequence semantics.

    Used only if rules.py is imported without run.py on the path (tests).
    Identical policy: respect single/double quotes, honour backslash
    escapes, split on unquoted ``;``, ``&&``, ``||``, ``|``.
    """
    out: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    i = 0
    n = len(cmd)
    while i < n:
        c = cmd[i]
        if c == "\\" and i + 1 < n:
            buf.append(cmd[i : i + 2])
            i += 2
            continue
        if c == "'" and not in_double:
            in_single = not in_single
            buf.append(c)
            i += 1
            continue
        if c == '"' and not in_single:
            in_double = not in_double
            buf.append(c)
            i += 1
            continue
        if not in_single and not in_double:
            matched_op = None
            for op in _FALLBACK_SEQUENCE_OPS:
                if cmd.startswith(op, i):
                    matched_op = op
                    break
            if matched_op is not None:
                out.append("".join(buf).strip())
                buf = []
                i += len(matched_op)
                continue
        buf.append(c)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return [s for s in out if s]


def _split(cmd: str) -> list[str]:
    if _split_sequence is not None:
        return _split_sequence(cmd)
    return _fallback_split_sequence(cmd)


def extract_sub_commands(command: str) -> list[str]:
    """Return the list of effective sub-command strings for predicate matching.

    If ``command`` is ``bash -c "<inner>"`` (or ``-lc``), return the split of
    ``<inner>`` on sequence operators. Otherwise return the pipeline-split
    of ``command`` itself — so ``ctl list users | grep foo`` yields two
    sub-commands just like ``bash -c "ctl list users | grep foo"`` does.
    """
    stripped = (command or "").strip()
    if not stripped:
        return []

    # Detect bash -c / bash -lc and peel the inner script.
    try:
        tokens = shlex.split(stripped, comments=False, posix=True)
    except ValueError:
        # Unbalanced quotes etc. — treat the raw string as its own sub-command.
        return [stripped]

    if (
        len(tokens) >= 3
        and tokens[0] == "bash"
        and tokens[1] in ("-c", "-lc")
    ):
        inner = tokens[2]
        return _split(inner) or [inner]

    # Not a bash -c wrapper; still split on sequence operators so pipelines
    # the harness happened to accept inline (unlikely post-allowlist, but
    # possible in synthetic tests) are handled consistently.
    parts = _split(stripped)
    return parts or [stripped]


# ---------------------------------------------------------------------------
# Predicate matching
# ---------------------------------------------------------------------------


class _RuleError(Exception):
    """Raised by the evaluator for a single rule item; caught per-item so
    a bad regex doesn't crash the rest of the evaluation."""


def _compile_regex(pattern: str, *, case_sensitive: bool = True) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        raise _RuleError(f"regex compile error: {e}") from e


def _subcommand_matches_predicate(
    sub_cmd: str,
    match: dict[str, Any],
    *,
    exit_code: int | None,
    stdout: str,
    stderr: str,
) -> bool:
    """True iff `sub_cmd` satisfies every specified predicate field.

    `match` is a dict with optional keys:
        argv_prefix, argv_regex, stdout_regex, stderr_regex, exit_code.
    AND semantics: a missing key imposes no constraint, but every present
    key must match. An empty predicate returns True for any sub-command.
    """
    # argv_prefix — tokens start-with check.
    argv_prefix = match.get("argv_prefix")
    if argv_prefix is not None:
        try:
            tokens = shlex.split(sub_cmd, comments=False, posix=True)
        except ValueError:
            return False
        if not isinstance(argv_prefix, (list, tuple)):
            raise _RuleError("argv_prefix must be a list of strings")
        if len(tokens) < len(argv_prefix):
            return False
        for expected, actual in zip(argv_prefix, tokens):
            if expected != actual:
                return False

    # argv_regex — regex over the full sub-command string.
    argv_regex = match.get("argv_regex")
    if argv_regex is not None:
        pat = _compile_regex(str(argv_regex))
        if not pat.search(sub_cmd):
            return False

    # stdout_regex / stderr_regex — regex over captured streams for the
    # original (whole) tool call. We don't slice these per sub-command —
    # the harness only captures stdout/stderr once per tool call, so the
    # whole output is what's available.
    stdout_regex = match.get("stdout_regex")
    if stdout_regex is not None:
        pat = _compile_regex(str(stdout_regex))
        if not pat.search(stdout or ""):
            return False

    stderr_regex = match.get("stderr_regex")
    if stderr_regex is not None:
        pat = _compile_regex(str(stderr_regex))
        if not pat.search(stderr or ""):
            return False

    # exit_code — exact int match. None (e.g. rejected / timed out) never
    # matches a concrete expected code.
    expected_code = match.get("exit_code")
    if expected_code is not None:
        if exit_code is None:
            return False
        try:
            if int(exit_code) != int(expected_code):
                return False
        except (TypeError, ValueError):
            return False

    return True


def _tool_call_matches_predicate(
    call: dict[str, Any], match: dict[str, Any] | None
) -> tuple[bool, str | None]:
    """Decide whether a single transcript tool call matches `match`.

    Returns (matched, matched_sub_command). `matched_sub_command` is the
    sub-command string that satisfied the predicate (useful for
    `triggered_by` reporting); it may equal the whole command for calls
    that weren't `bash -c` wrappers.
    """
    if match is None:
        match = {}
    command = call.get("command") or ""
    if not isinstance(command, str):
        command = str(command)
    exit_code = call.get("exit_code")
    stdout = call.get("stdout") or ""
    stderr = call.get("stderr") or ""

    for sub in extract_sub_commands(command):
        if _subcommand_matches_predicate(
            sub,
            match,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        ):
            return True, sub
    return False, None


def _call_snippet(call: dict[str, Any], matched_sub: str | None) -> dict[str, Any]:
    """Small, JSON-safe summary of a tool call for the ``triggered_by`` field."""
    cmd = call.get("command") or ""
    return {
        "turn": call.get("turn"),
        "command": cmd,
        "matched_sub_command": matched_sub if matched_sub and matched_sub != cmd else None,
        "exit_code": call.get("exit_code"),
    }


# ---------------------------------------------------------------------------
# Per-assertion evaluators
# ---------------------------------------------------------------------------


def _eval_tool_called(item: dict[str, Any], tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    match = item.get("match") or {}
    for call in tool_calls:
        ok, sub = _tool_call_matches_predicate(call, match)
        if ok:
            return {
                "pass": True,
                "triggered_by": _call_snippet(call, sub),
                "note": "matching tool call found",
            }
    return {
        "pass": False,
        "triggered_by": None,
        "note": "no tool call matched the predicate",
    }


def _eval_no_tool_called(
    item: dict[str, Any], tool_calls: list[dict[str, Any]]
) -> dict[str, Any]:
    match = item.get("match") or {}
    for call in tool_calls:
        ok, sub = _tool_call_matches_predicate(call, match)
        if ok:
            return {
                "pass": False,
                "triggered_by": _call_snippet(call, sub),
                "note": "forbidden tool call was made",
            }
    return {
        "pass": True,
        "triggered_by": None,
        "note": "no matching call — as required",
    }


def _eval_tool_sequence(
    item: dict[str, Any], tool_calls: list[dict[str, Any]]
) -> dict[str, Any]:
    sequence = item.get("sequence")
    if not isinstance(sequence, list) or not sequence:
        raise _RuleError("tool_sequence requires a non-empty `sequence` list")

    last_matched: dict[str, Any] | None = None
    last_sub: str | None = None
    cursor = 0  # index into tool_calls; calls consumed in order

    for step_idx, step_pred in enumerate(sequence):
        if not isinstance(step_pred, dict):
            raise _RuleError(
                f"sequence[{step_idx}] must be a mapping of predicate fields"
            )
        found = False
        while cursor < len(tool_calls):
            call = tool_calls[cursor]
            ok, sub = _tool_call_matches_predicate(call, step_pred)
            cursor += 1
            if ok:
                found = True
                last_matched = call
                last_sub = sub
                break
        if not found:
            return {
                "pass": False,
                "triggered_by": _call_snippet(last_matched, last_sub)
                if last_matched is not None
                else None,
                "note": (
                    f"sequence broke at step {step_idx} — no subsequent tool call "
                    f"matched that step's predicate"
                ),
            }

    return {
        "pass": True,
        "triggered_by": _call_snippet(last_matched, last_sub)
        if last_matched is not None
        else None,
        "note": "all sequence steps matched in order",
    }


def _eval_final_text_regex(
    item: dict[str, Any], final_text: str
) -> dict[str, Any]:
    pattern = item.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        raise _RuleError("final_text_regex requires a non-empty `pattern`")
    case_sensitive = bool(item.get("case_sensitive", False))
    pat = _compile_regex(pattern, case_sensitive=case_sensitive)
    m = pat.search(final_text or "")
    if m:
        start = max(0, m.start() - 20)
        end = min(len(final_text or ""), m.end() + 20)
        return {
            "pass": True,
            "triggered_by": {"final_text_snippet": (final_text or "")[start:end]},
            "note": "final_text matched the regex",
        }
    return {
        "pass": False,
        "triggered_by": None,
        "note": "final_text did not match the regex",
    }


def _eval_final_text_contains(
    item: dict[str, Any], final_text: str
) -> dict[str, Any]:
    text = item.get("text")
    if not isinstance(text, str) or not text:
        raise _RuleError("final_text_contains requires a non-empty `text`")
    case_sensitive = bool(item.get("case_sensitive", False))
    haystack = final_text or ""
    if not case_sensitive:
        found = text.lower() in haystack.lower()
    else:
        found = text in haystack
    if found:
        # Find the position for snippet context (case-insensitive lookup).
        hay_for_pos = haystack if case_sensitive else haystack.lower()
        needle = text if case_sensitive else text.lower()
        idx = hay_for_pos.find(needle)
        start = max(0, idx - 20)
        end = min(len(haystack), idx + len(needle) + 20)
        return {
            "pass": True,
            "triggered_by": {"final_text_snippet": haystack[start:end]},
            "note": "final_text contained the required substring",
        }
    return {
        "pass": False,
        "triggered_by": None,
        "note": "final_text did not contain the required substring",
    }


def _eval_exit_code_seen(
    item: dict[str, Any], tool_calls: list[dict[str, Any]]
) -> dict[str, Any]:
    match = dict(item.get("match") or {})
    if "exit_code" not in match:
        raise _RuleError("exit_code_seen requires `match.exit_code`")
    for call in tool_calls:
        ok, sub = _tool_call_matches_predicate(call, match)
        if ok:
            return {
                "pass": True,
                "triggered_by": _call_snippet(call, sub),
                "note": f"saw matching call with exit_code={match['exit_code']}",
            }
    return {
        "pass": False,
        "triggered_by": None,
        "note": "no matching call exited with the required code",
    }


_ASSERT_HANDLERS = {
    "tool_called": _eval_tool_called,
    "no_tool_called": _eval_no_tool_called,
    "tool_sequence": _eval_tool_sequence,
    "final_text_regex": _eval_final_text_regex,
    "final_text_contains": _eval_final_text_contains,
    "exit_code_seen": _eval_exit_code_seen,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def evaluate_rule_check(
    rule_items: list[dict[str, Any]],
    transcript: dict[str, Any],
) -> dict[str, Any]:
    """Grade `rule_items` against a transcript produced by ``run.py``.

    Returns a dict with:
        items          : list of per-rule results
                         ({"id", "assert", "pass", "triggered_by", "weight",
                           "note"})
        total_weight   : sum of weights across all items
        passed_weight  : sum of weights for items that passed
    """
    tool_calls = transcript.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        tool_calls = []
    final_text = transcript.get("final_text") or ""
    if not isinstance(final_text, str):
        final_text = str(final_text)

    results: list[dict[str, Any]] = []
    total_weight = 0
    passed_weight = 0

    for raw_item in rule_items or []:
        item = raw_item if isinstance(raw_item, dict) else {}
        rid = item.get("id", "")
        assert_kind = item.get("assert", "")
        try:
            weight = int(item.get("weight", 1))
        except (TypeError, ValueError):
            weight = 1
        total_weight += weight

        handler = _ASSERT_HANDLERS.get(assert_kind)
        if handler is None:
            results.append(
                {
                    "id": rid,
                    "assert": assert_kind,
                    "pass": False,
                    "triggered_by": None,
                    "weight": weight,
                    "note": f"unknown assert type: {assert_kind!r}",
                }
            )
            continue

        try:
            if assert_kind in ("final_text_regex", "final_text_contains"):
                verdict = handler(item, final_text)  # type: ignore[arg-type]
            else:
                verdict = handler(item, tool_calls)  # type: ignore[arg-type]
        except _RuleError as e:
            results.append(
                {
                    "id": rid,
                    "assert": assert_kind,
                    "pass": False,
                    "triggered_by": None,
                    "weight": weight,
                    "note": str(e),
                }
            )
            continue
        except Exception as e:  # defensive: never crash the whole evaluation
            results.append(
                {
                    "id": rid,
                    "assert": assert_kind,
                    "pass": False,
                    "triggered_by": None,
                    "weight": weight,
                    "note": f"evaluation error: {type(e).__name__}: {e}",
                }
            )
            continue

        passed = bool(verdict.get("pass"))
        if passed:
            passed_weight += weight
        results.append(
            {
                "id": rid,
                "assert": assert_kind,
                "pass": passed,
                "triggered_by": verdict.get("triggered_by"),
                "weight": weight,
                "note": verdict.get("note", ""),
            }
        )

    return {
        "items": results,
        "total_weight": total_weight,
        "passed_weight": passed_weight,
    }


__all__ = ["evaluate_rule_check", "extract_sub_commands"]
