#!/usr/bin/env python3
"""Smoke test for harness/run.py:load_skill_index.

Builds a temporary `skills/` directory with three valid skill files plus a
README and a malformed file, then verifies:
  - bodies dict has every valid skill keyed by name
  - bodies do NOT contain the frontmatter block
  - index is sorted by name and lists (name, description) pairs
  - README.md is skipped
  - non-frontmatter docs are skipped silently
  - a skill whose `name` doesn't match its filename raises a clear error
  - a skill with a description over 250 chars raises a clear error

Run directly:

    python harness/_test_load_skill_index.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path


HARNESS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))

from run import load_skill_index  # noqa: E402


FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


SKILL_A = """---
name: skill-a
description: First test skill — used to validate the loader.
---

# Skill A

Body of skill A.
"""

SKILL_B = """---
name: skill-b
description: Second test skill — sorts after skill-a.
---

# Skill B

Body of skill B with multiple lines.

End.
"""

SKILL_C = """---
name: alpha-skill
description: Third test skill — sorts before everyone else.
---

# Alpha
"""

# Plain markdown without frontmatter — must be ignored silently.
DOC_ONLY = """# Just docs

This file has no frontmatter and is documentation, not a skill.
"""

# README must be ignored unconditionally.
README_TEXT = """# Skills

This is the skills directory README.
"""


def run_happy_path() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="skills_test_"))
    try:
        write(tmp / "skill-a.md", SKILL_A)
        write(tmp / "skill-b.md", SKILL_B)
        write(tmp / "alpha-skill.md", SKILL_C)
        write(tmp / "README.md", README_TEXT)
        write(tmp / "notes.md", DOC_ONLY)

        bodies, index = load_skill_index(tmp)

        check(
            "1a: index has exactly the three valid skills",
            sorted(n for n, _ in index) == ["alpha-skill", "skill-a", "skill-b"],
            detail=f"got {[n for n, _ in index]}",
        )
        check(
            "1b: index sorted alphabetically by name",
            [n for n, _ in index] == ["alpha-skill", "skill-a", "skill-b"],
        )
        check(
            "1c: bodies dict keyed by name with same set as index",
            set(bodies.keys()) == {"alpha-skill", "skill-a", "skill-b"},
        )
        check(
            "1d: body excludes the frontmatter block",
            "---" not in bodies["skill-a"].splitlines()[0],
        )
        check(
            "1e: body content preserved",
            "Body of skill A." in bodies["skill-a"]
            and "End." in bodies["skill-b"],
        )
        check(
            "1f: description matches frontmatter",
            dict(index)["skill-a"].startswith("First test skill"),
        )
        check(
            "1g: README.md is skipped",
            "README" not in bodies and not any(n == "README" for n, _ in index),
        )
        check(
            "1h: non-frontmatter docs are skipped silently",
            "notes" not in bodies,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_name_mismatch() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="skills_test_"))
    try:
        # filename stem is "renamed-skill", frontmatter says "skill-x" — mismatch.
        write(
            tmp / "renamed-skill.md",
            """---
name: skill-x
description: Mismatched name.
---

Body
""",
        )
        try:
            load_skill_index(tmp)
        except RuntimeError as e:
            msg = str(e)
            check(
                "2a: filename/name mismatch raises a clear error",
                "renamed-skill" in msg and "skill-x" in msg,
                detail=f"got: {msg}",
            )
            return
        check("2a: filename/name mismatch raises a clear error", False, "no exception raised")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_long_description() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="skills_test_"))
    try:
        long_desc = "x" * 251
        write(
            tmp / "too-long.md",
            f"""---
name: too-long
description: {long_desc}
---

Body
""",
        )
        try:
            load_skill_index(tmp)
        except RuntimeError as e:
            msg = str(e)
            check(
                "3a: description over 250 chars raises a clear error",
                "251" in msg and "250" in msg,
                detail=f"got: {msg}",
            )
            return
        check("3a: description over 250 chars raises a clear error", False, "no exception raised")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_missing_dir() -> None:
    """Loading a non-existent directory returns empty results, not a raise."""
    tmp = Path(tempfile.mkdtemp(prefix="skills_test_"))
    shutil.rmtree(tmp)
    bodies, index = load_skill_index(tmp)
    check(
        "4a: missing skills_dir returns empty (bodies, index)",
        bodies == {} and index == [],
    )


run_happy_path()
run_name_mismatch()
run_long_description()
run_missing_dir()

print()
if FAILURES:
    print(f"FAILED {len(FAILURES)} case(s): {FAILURES}")
    sys.exit(1)
print("all load_skill_index cases passed")
sys.exit(0)
