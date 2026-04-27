"""
Per-bucket schema sanity check for the task library.

Verifies the migration of buckets 001-025 (stateful), 051-070 (long-horizon),
and 071-085 (unplanted-failure) from judge_rubric to rule_check / hybrid.

Run from repo root:
    python harness/_test_task_rules.py
"""

import pathlib
import re
import sys

import yaml

TASKS_DIR = pathlib.Path(__file__).resolve().parent.parent / "tasks"

# Ranges that were migrated (inclusive).
STATEFUL = set(f"{i:03d}" for i in range(1, 26))         # pure rule_check
LONG_HORIZON = set(f"{i:03d}" for i in range(51, 71))    # hybrid (rule_check + judge_rubric)
UNPLANTED = set(f"{i:03d}" for i in range(71, 86))       # pure rule_check

# Ranges that were left untouched.
AMBIGUOUS = set(f"{i:03d}" for i in range(26, 51))       # judge_rubric only
NON_FILE = set(f"{i:03d}" for i in range(86, 101))       # judge_rubric only

PURE_RULES = STATEFUL | UNPLANTED
HYBRID = LONG_HORIZON
JUDGE_ONLY = AMBIGUOUS | NON_FILE


def _valid_rule_check(rc):
    """Lightweight structural check on a rule_check block."""
    errors = []
    if not isinstance(rc, list) or not rc:
        return ["rule_check is empty or not a list"]
    if not (2 <= len(rc) <= 8):
        errors.append(f"rule_check item count {len(rc)} outside [2, 8]")
    total_weight = sum(int(item.get("weight", 0)) for item in rc)
    if not (3 <= total_weight <= 9):
        errors.append(f"rule_check total weight {total_weight} outside [3, 9]")
    for item in rc:
        iid = item.get("id", "<unknown>")
        assert_type = item.get("assert")
        if assert_type not in {
            "tool_called",
            "no_tool_called",
            "tool_sequence",
            "final_text_regex",
            "final_text_contains",
            "exit_code_seen",
        }:
            errors.append(f"{iid}: unknown assert {assert_type!r}")
        match = item.get("match") or {}
        for key in ("argv_regex", "stdout_regex", "stderr_regex"):
            rx = match.get(key)
            if rx:
                try:
                    re.compile(rx)
                except re.error as exc:
                    errors.append(f"{iid}.{key}: invalid regex: {exc}")
        pat = item.get("pattern")
        if pat:
            try:
                re.compile(pat)
            except re.error as exc:
                errors.append(f"{iid}.pattern: invalid regex: {exc}")
        for step in item.get("sequence", []) or []:
            rx = step.get("argv_regex")
            if rx:
                try:
                    re.compile(rx)
                except re.error as exc:
                    errors.append(f"{iid}.sequence: invalid regex: {exc}")
    return errors


def main() -> int:
    failures = 0
    seen_ids = set()
    for path in sorted(TASKS_DIR.glob("[0-9][0-9][0-9]-*.yaml")):
        try:
            task = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            print(f"{path.name}: YAML parse error: {exc}")
            failures += 1
            continue

        tid = str(task.get("id", "")).zfill(3)
        seen_ids.add(tid)
        has_rc = "rule_check" in task and task["rule_check"]
        has_jr = "judge_rubric" in task and task["judge_rubric"]

        if tid == "000":  # stub
            continue

        if tid in PURE_RULES:
            if not has_rc:
                print(f"{path.name}: missing rule_check (bucket expects pure rule_check)")
                failures += 1
            if has_jr:
                print(f"{path.name}: has judge_rubric but bucket expects pure rule_check")
                failures += 1
            if has_rc:
                for msg in _valid_rule_check(task["rule_check"]):
                    print(f"{path.name}: {msg}")
                    failures += 1

        elif tid in HYBRID:
            if not has_rc:
                print(f"{path.name}: missing rule_check (hybrid task)")
                failures += 1
            if not has_jr:
                print(f"{path.name}: missing judge_rubric (hybrid task)")
                failures += 1
            if has_rc:
                for msg in _valid_rule_check(task["rule_check"]):
                    print(f"{path.name}: {msg}")
                    failures += 1

        elif tid in JUDGE_ONLY:
            if has_rc:
                print(f"{path.name}: has rule_check but bucket expects judge_rubric only")
                failures += 1
            if not has_jr:
                print(f"{path.name}: missing judge_rubric")
                failures += 1

        else:
            print(f"{path.name}: id {tid} outside known ranges")
            failures += 1

    expected = set(f"{i:03d}" for i in range(1, 101))
    missing = expected - seen_ids
    if missing:
        print(f"missing task ids: {sorted(missing)}")
        failures += len(missing)

    if failures:
        print(f"FAIL: {failures} issue(s)")
        return 1
    print(f"OK: {len(seen_ids)} tasks validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
