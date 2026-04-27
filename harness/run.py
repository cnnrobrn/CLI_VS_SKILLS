#!/usr/bin/env python3
"""CLI_VS_SKILLS harness runner.

Drives the OpenRouter API (via the OpenAI-compatible SDK) against benchmark
tasks in either the `cli-only` or `cli-skills` arm. For each
(task x arm x trial) combination it:

  1. Creates a fresh per-trial workdir and CTL_STATE_DIR (state never leaks
     between runs).
  2. Executes any task.setup commands (same allowlisted bash pipeline — NOT
     exposed to the agent; recorded in the transcript).
  3. Builds a system prompt describing the environment. For `cli-only`, it
     appends cli/README.md (or a one-liner stub if that file is missing). For
     `cli-skills`, it additionally appends the full skills/SKILLS.md under a
     clearly delimited header.
  4. Passes the task prompt as the sole user message.
  5. Gives the agent a single `bash` tool. Commands are filtered against a
     strict allowlist; rejected commands are returned to the agent as
     structured tool errors so it can recover.
  6. Loops for up to max_turns until the agent stops calling tools.
  7. Writes a complete transcript to <out>/<task>/<arm>/trial_<n>/transcript.json
     including the final assistant message (`final_text`) that the judge grades.
  8. Heuristically copies any /tmp/task-*.* paths mentioned in the user prompt
     into the workdir as `artifact.<ext>` so downstream inspection doesn't
     have to trust /tmp to survive.

Run `python harness/run.py --help` for flags. See harness/README.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Paths and config
# ---------------------------------------------------------------------------

HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_DIR.parent
DEFAULT_CONFIG_PATH = HARNESS_DIR / "config.yaml"


def load_config(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# System-prompt assembly
# ---------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """You are an autonomous agent being evaluated on a benchmark.

Environment:
- Your working directory is a repo root. You have ONE tool: `bash`.
- A custom CLI named `ctl` lives at ./cli/bin/ctl (also reachable as `ctl`).
- The CLI reads canned fixtures from disk and does NOT access the network.
- The CLI honors a pinned "now" of 2026-04-24T00:00:00Z for --since filters.
- Allowed executables: ./cli/bin/ctl, ctl, cat, ls, mkdir, head, tail, wc,
  grep, jq, python3, echo, bash (only as `bash -c "..."`, and the inner
  command is re-checked against the same allowlist).
- You MAY redirect output to files under /tmp/ (and under $CTL_STATE_DIR).
- Pipes (|), command chaining (;, &&, ||), and command substitution
  ($(...) or backticks) inside a single command string are NOT allowed.
  If you need to combine operations, wrap the whole line in
  `bash -c "cmd1 && cmd2"` — each sub-command still has to pass the
  allowlist.
- Each command has a {timeout}-second timeout.

Task rules:
- Follow the user's instructions exactly. Where the task asks you to write
  output to a specific file path, write EXACTLY to that path.
- If a command fails, read the error and try a different approach. Do not
  retry the same failing command unchanged.
- When you are finished, stop calling tools and provide a short final
  answer. Many tasks will be graded on that final message, so be precise —
  name IDs, files, and root causes explicitly.
"""

CLI_ONLY_REFERENCE_HEADER = """## Reference: cli/README.md

The following is the complete contents of cli/README.md. It is the only
documentation you have for the `ctl` CLI. Discover any further behavior by
running `ctl --help` and `ctl <subcommand> --help`.

"""

CLI_ONLY_STUB_REFERENCE = """## Reference

cli/README.md does not exist yet. See `./cli/bin/ctl --help` for available
subcommands.
"""

CLI_SKILLS_INDEX_HEADER = """## Available skills

You have access to a library of skills, each addressing a specific class of problem you might encounter while using `ctl`. Below is the index of every skill — only the names and one-line descriptions are shown here. To read a skill's full content, call the `load_skill` tool with `name=<skill name>`. Load only skills that look relevant to the current task.

"""


# Frontmatter contract: each skill .md file starts with a YAML block delimited
# by two lines containing only `---`. The block must define `name` (string)
# and `description` (string, max 250 chars). The body is everything after the
# closing `---`.
_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<front>.*?)\n---\s*\n?(?P<body>.*)",
    re.DOTALL,
)
_DESCRIPTION_MAX_CHARS = 250


def _parse_skill_file(path: Path) -> tuple[str, str, str] | None:
    """Parse one skill file. Returns (name, description, body) on success.

    Returns None for files that don't have a parseable frontmatter block —
    those are treated as documentation, not skills, and silently skipped
    (per the contract, `skills/README.md` is documentation for humans).

    Raises RuntimeError on a file that DOES have frontmatter but whose
    metadata is invalid (missing fields, wrong types, name/filename mismatch,
    description too long). Fail fast — a malformed skill file is a bug.
    """
    text = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None
    front_raw = m.group("front")
    body = m.group("body")
    try:
        front = yaml.safe_load(front_raw)
    except yaml.YAMLError as e:
        raise RuntimeError(f"skill {path.name}: frontmatter YAML parse error: {e}")
    if not isinstance(front, dict):
        raise RuntimeError(
            f"skill {path.name}: frontmatter must be a YAML mapping (got {type(front).__name__})"
        )
    name = front.get("name")
    description = front.get("description")
    if not isinstance(name, str) or not name.strip():
        raise RuntimeError(f"skill {path.name}: frontmatter is missing a string `name`")
    if not isinstance(description, str) or not description.strip():
        raise RuntimeError(
            f"skill {path.name}: frontmatter is missing a string `description`"
        )
    if len(description) > _DESCRIPTION_MAX_CHARS:
        raise RuntimeError(
            f"skill {path.name}: description is {len(description)} chars; "
            f"limit is {_DESCRIPTION_MAX_CHARS}"
        )
    expected_stem = path.stem
    if name != expected_stem:
        raise RuntimeError(
            f"skill {path.name}: frontmatter name {name!r} must equal "
            f"the filename stem {expected_stem!r}"
        )
    return name, description, body


def load_skill_index(
    skills_dir: Path,
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Load every skill file under `skills_dir` (non-recursive).

    Returns:
      bodies: {name -> body_text} — body excludes the frontmatter block.
      index:  [(name, description), ...] sorted by name for stable rendering.

    Skips `README.md` and any file that doesn't have parseable frontmatter
    (those are docs for humans). Fails fast on a file that looks like a skill
    but has invalid metadata.
    """
    if not skills_dir.exists() or not skills_dir.is_dir():
        return {}, []
    bodies: dict[str, str] = {}
    rows: list[tuple[str, str]] = []
    for p in sorted(skills_dir.glob("*.md")):
        if p.name == "README.md":
            continue
        parsed = _parse_skill_file(p)
        if parsed is None:
            # No frontmatter — treat as docs, skip silently.
            continue
        name, description, body = parsed
        if name in bodies:
            raise RuntimeError(
                f"duplicate skill name {name!r}: seen in {p.name} and earlier file"
            )
        bodies[name] = body
        rows.append((name, description))
    rows.sort(key=lambda r: r[0])
    return bodies, rows


def render_skill_index_block(index: list[tuple[str, str]]) -> str:
    """Format the skill-index bullet list that goes into the system prompt."""
    lines = [CLI_SKILLS_INDEX_HEADER.rstrip()]
    lines.append("")
    for name, desc in index:
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines) + "\n"


def build_system_prompt(
    arm: str,
    *,
    cli_readme_text: str | None,
    skill_index: list[tuple[str, str]] | None,
    timeout_s: int,
) -> str:
    parts = [BASE_SYSTEM_PROMPT.format(timeout=timeout_s)]
    # Every arm gets cli/README.md (or a stub) so the baseline is the same.
    if cli_readme_text and cli_readme_text.strip():
        parts.append(CLI_ONLY_REFERENCE_HEADER)
        parts.append(cli_readme_text)
    else:
        parts.append(CLI_ONLY_STUB_REFERENCE)

    if arm == "cli-skills":
        if not skill_index:
            raise RuntimeError(
                "cli-skills arm requested but no skills were loaded from skills/"
            )
        parts.append(render_skill_index_block(skill_index))
    elif arm != "cli-only":
        raise ValueError(f"unknown arm: {arm!r}")

    return "\n".join(parts)


def load_file_text(path: Path) -> str | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return text if text.strip() else None


# ---------------------------------------------------------------------------
# Command allowlist
# ---------------------------------------------------------------------------

# Operators that split a line into sequentially-evaluated sub-commands. We
# validate each sub-command recursively against the same allowlist.
_SEQUENCE_OPS = [";", "&&", "||", "|"]

# Redirect pattern used to detect `>`/`>>` writes.
_REDIRECT_RE = re.compile(r"(?P<op>>>?)\s*(?P<path>\S+)")

# Forbidden metacharacters that cannot be made safe by sub-command validation.
_HARD_FORBIDDEN = [
    ("`", "command substitution with backticks is not allowed"),
    ("$(", "$(...) command substitution is not allowed"),
    ("<(", "process substitution is not allowed"),
    (">(", "process substitution is not allowed"),
]

# Files / paths that must never be readable from inside an agent transcript.
# Matching is on the basename and on suffix patterns; checked against every
# token of the parsed argv so `cat foo/.env` and `head -n5 ./.env.local` both fail.
_FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"(^|/)\.env(\.[^/]*)?$"),       # .env, .env.local, etc.
    re.compile(r"(^|/)id_rsa(\.pub)?$"),
    re.compile(r"(^|/)id_ed25519(\.pub)?$"),
    re.compile(r"(^|/)\.netrc$"),
    re.compile(r"(^|/)credentials(\.json|\.yaml|\.yml|\.txt)?$", re.I),
]

# Redaction patterns applied to stdout/stderr before they are recorded into
# the transcript. Defense in depth — even if an agent finds a sneaky way to
# read a secret, it shouldn't end up serialized to disk.
_REDACTION_PATTERNS = [
    (re.compile(r"sk-or-v1-[A-Za-z0-9]{32,}"), "sk-or-v1-[REDACTED]"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{32,}"), "sk-ant-[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9]{40,}"), "sk-[REDACTED]"),
    (re.compile(r"(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|HF_TOKEN|GITHUB_TOKEN)\s*=\s*\S+"),
     r"\1=[REDACTED]"),
    (re.compile(r"(Authorization:\s*Bearer)\s+\S+"), r"\1 [REDACTED]"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "ghp_[REDACTED]"),
    (re.compile(r"gho_[A-Za-z0-9]{30,}"), "gho_[REDACTED]"),
    (re.compile(r"AKIA[A-Z0-9]{16}"), "AKIA[REDACTED]"),
]


def _argv_token_is_forbidden_path(token: str) -> str | None:
    """Return the matched pattern if `token` references a sensitive file."""
    for pat in _FORBIDDEN_PATH_PATTERNS:
        if pat.search(token):
            return pat.pattern
    return None


def redact_secrets(text: str) -> str:
    """Apply redaction patterns to text. Idempotent."""
    if not text:
        return text
    for pat, replacement in _REDACTION_PATTERNS:
        text = pat.sub(replacement, text)
    return text


@dataclass
class CommandDecision:
    allowed: bool
    reason: str = ""
    # Execute through `bash -c` when redirects or explicit bash -c usage are
    # present; otherwise run the argv directly (safer, no shell).
    use_shell: bool = False


def _split_sequence(cmd: str) -> list[str]:
    """Split a shell-ish command string on sequence operators, respecting
    single- and double-quoted strings. Returns a list of sub-commands.

    We do NOT try to be a full shell parser; we only need to find unquoted
    ;, &&, ||, | so we can re-validate each sub-command's argv[0].
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
            # Keep escaped chars with their escape.
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
            for op in _SEQUENCE_OPS:
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


def _expand_writable_prefixes(prefixes: list[str], env: dict[str, str]) -> list[str]:
    """Expand $CTL_STATE_DIR / $WORKDIR / other envvars in writable prefixes.

    Prefixes that reference an undefined env var are dropped with a warning —
    we don't want '$WORKDIR' to match a literal path like '$WORKDIRfoo'.
    """
    expanded: list[str] = []
    for p in prefixes:
        if "$" in p:
            resolved = os.path.expandvars(p)
            if resolved == p or not resolved:
                # Unexpanded. Skip — better to reject writes than allow by accident.
                continue
            expanded.append(resolved.rstrip("/") + "/")
        else:
            # Normalize trailing slash for consistent startswith checks.
            expanded.append(p if p.endswith("/") else p + "/")
    return expanded


def _validate_redirects(cmd: str, writable_prefixes: list[str]) -> tuple[bool, str]:
    """Every `>`/`>>` target in cmd must start with a writable prefix."""
    has_any = False
    for match in _REDIRECT_RE.finditer(cmd):
        has_any = True
        target = match.group("path")
        # Strip surrounding quotes if any.
        if (target.startswith("'") and target.endswith("'")) or (
            target.startswith('"') and target.endswith('"')
        ):
            target = target[1:-1]
        if not any(target.startswith(pfx) for pfx in writable_prefixes):
            return (
                False,
                f"redirect target {target!r} must start with one of {writable_prefixes}",
            )
    return (True, "")


def decide_command(
    command: str,
    allowed_argv0: list[str],
    writable_prefixes: list[str],
    *,
    _depth: int = 0,
) -> CommandDecision:
    """Decide whether to run `command`.

    Policy:
      * argv[0] must be EXACTLY one of `allowed_argv0`.
      * Redirects (>/ >>) must target paths under writable_prefixes.
      * If the command is `bash -c "<inner>"`, recursively validate <inner>.
        Each sub-command of <inner> (split on ;, &&, ||, |) must also pass.
      * Command substitution ($(), ``) and process substitution (<(), >()) are
        always rejected — we can't meaningfully sandbox them.
    """
    if _depth > 3:
        return CommandDecision(False, "command nesting too deep")

    stripped = command.strip()
    if not stripped:
        return CommandDecision(False, "empty command")

    # Hard rejections: these can't be recovered by recursive validation.
    for token, msg in _HARD_FORBIDDEN:
        if token in stripped:
            return CommandDecision(False, msg)

    # Redirect targets must be writable. Validate across the whole string.
    ok, reason = _validate_redirects(stripped, writable_prefixes)
    if not ok:
        return CommandDecision(False, reason)

    # Split on sequence operators; validate every sub-command recursively.
    sub_cmds = _split_sequence(stripped)
    if len(sub_cmds) > 1:
        for sc in sub_cmds:
            d = decide_command(
                sc,
                allowed_argv0,
                writable_prefixes,
                _depth=_depth + 1,
            )
            if not d.allowed:
                return CommandDecision(
                    False,
                    f"sub-command {sc!r} rejected: {d.reason}",
                )
        # Combining multiple sub-commands needs a shell.
        return CommandDecision(True, use_shell=True)

    # Single sub-command path — tokenize and check argv[0].
    try:
        tokens = shlex.split(stripped, comments=False, posix=True)
    except ValueError as e:
        return CommandDecision(False, f"could not parse command: {e}")
    if not tokens:
        return CommandDecision(False, "empty command after parsing")

    argv0 = tokens[0]
    if argv0 not in allowed_argv0:
        return CommandDecision(
            False,
            f"argv[0]={argv0!r} is not in the allowlist. Allowed: {allowed_argv0}",
        )

    # Block reads of sensitive files. Check every non-flag token; this catches
    # `cat .env`, `head -n5 ./.env.local`, `python3 .env`, etc.
    for token in tokens[1:]:
        if token.startswith("-"):
            continue
        match = _argv_token_is_forbidden_path(token)
        if match is not None:
            return CommandDecision(
                False,
                f"reading {token!r} is forbidden (matches sensitive-path pattern {match!r})",
            )

    # Special case: `bash -c "<inner>"`. Validate the inner string recursively.
    if argv0 == "bash":
        # Accept exactly `bash -c <inner>` or `bash -lc <inner>`; nothing else.
        if len(tokens) < 3 or tokens[1] not in ("-c", "-lc"):
            return CommandDecision(
                False,
                "bash is only allowed as `bash -c \"<inner>\"` with an inner command",
            )
        inner = tokens[2]
        # If there are extra tokens after the inner script, treat them as
        # positional args — which bash would pass to the script as $0 $1 ...
        # We conservatively reject that to avoid edge cases.
        if len(tokens) > 3:
            return CommandDecision(
                False,
                "bash -c with trailing positional arguments is not allowed",
            )
        inner_decision = decide_command(
            inner,
            allowed_argv0,
            writable_prefixes,
            _depth=_depth + 1,
        )
        if not inner_decision.allowed:
            return CommandDecision(
                False,
                f"bash -c inner command rejected: {inner_decision.reason}",
            )
        return CommandDecision(True, use_shell=True)

    # Plain command. Use a shell only if we saw a redirect.
    has_redirect = bool(_REDIRECT_RE.search(stripped))
    return CommandDecision(True, use_shell=has_redirect)


# ---------------------------------------------------------------------------
# Bash tool execution
# ---------------------------------------------------------------------------


@dataclass
class ToolCallRecord:
    command: str
    allowed: bool
    rejection_reason: str
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    wall_clock_ms: int
    timed_out: bool


def _truncate(s: str, limit: int) -> tuple[str, bool]:
    s = redact_secrets(s)
    encoded = s.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return s, False
    return encoded[:limit].decode("utf-8", errors="replace"), True


def run_bash_command(
    command: str,
    *,
    allowed_argv0: list[str],
    writable_prefixes: list[str],
    timeout_s: int,
    cwd: Path,
    env: dict[str, str],
    stdout_cap: int,
    stderr_cap: int,
) -> ToolCallRecord:
    """Execute one command under the allowlist; return a structured record."""
    decision = decide_command(command, allowed_argv0, writable_prefixes)
    if not decision.allowed:
        return ToolCallRecord(
            command=command,
            allowed=False,
            rejection_reason=decision.reason,
            exit_code=None,
            stdout="",
            stderr="",
            stdout_truncated=False,
            stderr_truncated=False,
            wall_clock_ms=0,
            timed_out=False,
        )

    start = time.monotonic()
    try:
        if decision.use_shell:
            proc = subprocess.run(
                ["bash", "-c", command],
                cwd=str(cwd),
                env=env,
                capture_output=True,
                timeout=timeout_s,
                text=True,
            )
        else:
            tokens = shlex.split(command, posix=True)
            proc = subprocess.run(
                tokens,
                cwd=str(cwd),
                env=env,
                capture_output=True,
                timeout=timeout_s,
                text=True,
            )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout, stdout_trunc = _truncate(proc.stdout or "", stdout_cap)
        stderr, stderr_trunc = _truncate(proc.stderr or "", stderr_cap)
        return ToolCallRecord(
            command=command,
            allowed=True,
            rejection_reason="",
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_trunc,
            stderr_truncated=stderr_trunc,
            wall_clock_ms=elapsed_ms,
            timed_out=False,
        )
    except subprocess.TimeoutExpired as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = e.stdout or ""
        stderr = e.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stdout, stdout_trunc = _truncate(stdout, stdout_cap)
        stderr, stderr_trunc = _truncate(stderr, stderr_cap)
        return ToolCallRecord(
            command=command,
            allowed=True,
            rejection_reason="",
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_trunc,
            stderr_truncated=stderr_trunc,
            wall_clock_ms=elapsed_ms,
            timed_out=True,
        )
    except FileNotFoundError as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ToolCallRecord(
            command=command,
            allowed=True,
            rejection_reason="",
            exit_code=127,
            stdout="",
            stderr=f"executable not found: {e}",
            stdout_truncated=False,
            stderr_truncated=False,
            wall_clock_ms=elapsed_ms,
            timed_out=False,
        )


def tool_result_for(record: ToolCallRecord) -> str:
    """Format a ToolCallRecord as the content string the agent sees."""
    if not record.allowed:
        return (
            "ERROR: command rejected by harness allowlist.\n"
            f"reason: {record.rejection_reason}\n"
            "Allowed executables: ./cli/bin/ctl, ctl, cat, ls, mkdir, head, tail, "
            "wc, grep, jq, python3, echo, bash (as `bash -c \"...\"`). "
            "Redirects (>, >>) must target /tmp/ or $CTL_STATE_DIR. "
            "Command substitution (backticks, $()) and process substitution are "
            "never allowed."
        )
    if record.timed_out:
        return (
            f"ERROR: command timed out after {record.wall_clock_ms} ms.\n"
            f"Partial stdout:\n{record.stdout}\n"
            f"Partial stderr:\n{record.stderr}"
        )
    body = [f"exit_code: {record.exit_code}"]
    if record.stdout:
        suffix = " (truncated)" if record.stdout_truncated else ""
        body.append(f"stdout{suffix}:\n{record.stdout}")
    else:
        body.append("stdout: <empty>")
    if record.stderr:
        suffix = " (truncated)" if record.stderr_truncated else ""
        body.append(f"stderr{suffix}:\n{record.stderr}")
    return "\n".join(body)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


BASH_TOOL_DESCRIPTION = (
    "Run a single shell command in the repo root. Allowed executables: "
    "./cli/bin/ctl, ctl, cat, ls, mkdir, head, tail, wc, grep, jq, python3, "
    "echo, bash (only as `bash -c \"...\"`). Redirects to /tmp/ or "
    "$CTL_STATE_DIR are allowed with > or >>. Pipes and chaining (|, ;, &&, "
    "||) must be wrapped in bash -c; each sub-command is still validated. "
    "Command substitution ($(), ``) and process substitution are rejected. "
    "Per-command timeout is 30s."
)

# OpenAI Chat Completions tool format. OpenRouter (and any OpenAI-compatible
# gateway) speaks this shape regardless of the upstream provider.
BASH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": BASH_TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to run.",
                }
            },
            "required": ["command"],
        },
    },
}


# Skill-loading tool. Only attached to the cli-skills arm. The agent picks a
# name from the index in the system prompt; we return the full body as the
# tool result. Body text only counts against tokens when the agent loads it.
LOAD_SKILL_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "load_skill",
        "description": (
            "Load the full content of a skill by name. Call this when a skill "
            "in the index looks relevant to your current task. Returns the "
            "skill's body as plain markdown. Loading the same skill twice is "
            "allowed but wasteful."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The exact skill name from the index.",
                }
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
}


# Map OpenAI finish_reason values to the vocabulary the rest of the harness
# (and existing transcripts/judges) already use. "stop" == natural end;
# "length" == hit max_tokens; "tool_calls" == the model wants to invoke a tool.
_FINISH_REASON_MAP = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "content_filter",
    "function_call": "tool_use",  # legacy OpenAI name
}


def _map_finish_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    return _FINISH_REASON_MAP.get(reason, reason)


@dataclass
class RunResult:
    transcript: dict[str, Any]
    copied_artifacts: list[str]
    setup_failed: bool
    error: str | None = None


def _assistant_blocks_from_openai_message(msg: Any) -> list[dict[str, Any]]:
    """Render an OpenAI assistant message into the Anthropic-shaped content-
    block list this harness already stores in transcripts.

    We keep the same {type: "text", ...} / {type: "tool_use", ...} vocabulary
    so downstream tooling (judge.py renderer, scorers) doesn't need to change.
    """
    out: list[dict[str, Any]] = []
    text = getattr(msg, "content", None)
    if text:
        # OpenAI returns the assistant text as a single string (not blocks).
        out.append({"type": "text", "text": text})

    tool_calls = getattr(msg, "tool_calls", None) or []
    for tc in tool_calls:
        tc_id = getattr(tc, "id", "") or ""
        fn = getattr(tc, "function", None)
        name = getattr(fn, "name", "") if fn is not None else ""
        raw_args = getattr(fn, "arguments", "") if fn is not None else ""
        # OpenAI delivers tool-call arguments as a JSON-encoded STRING. Parse.
        if isinstance(raw_args, dict):
            parsed_input: Any = raw_args
        else:
            try:
                parsed_input = json.loads(raw_args) if raw_args else {}
            except json.JSONDecodeError:
                # Preserve the raw string so the transcript still shows what
                # the model tried to emit; the allowlist will reject it later.
                parsed_input = {"__raw_arguments__": raw_args}
        out.append(
            {
                "type": "tool_use",
                "id": tc_id,
                "name": name or "",
                "input": parsed_input,
            }
        )
    return out


def _final_assistant_text(messages: list[dict[str, Any]]) -> str:
    """Return the concatenated text of the last assistant message, if any.

    Works for both the content-block representation we store in transcripts
    and a bare-string content (which is how OpenAI natively represents
    assistant messages without tool calls).
    """
    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            stripped = content.strip()
            if stripped:
                return stripped
            continue
        if isinstance(content, list):
            parts: list[str] = []
            for b in content:
                if isinstance(b, dict) and b.get("type") == "text":
                    parts.append(b.get("text", ""))
            if parts:
                return "\n".join(p for p in parts if p).strip()
    return ""


# Heuristic: paths the agent is being told to write to (for artifact copy-out).
_TASK_PATH_RE = re.compile(r"/tmp/task-[A-Za-z0-9._/-]+")


def _extract_artifact_paths(prompt: str) -> list[str]:
    seen = []
    for m in _TASK_PATH_RE.finditer(prompt):
        p = m.group(0).rstrip(".,;:)]}'\"")
        if p not in seen:
            seen.append(p)
    return seen


def _run_setup_commands(
    commands: list[str],
    *,
    allowed_argv0: list[str],
    writable_prefixes: list[str],
    timeout_s: int,
    cwd: Path,
    env: dict[str, str],
    stdout_cap: int,
    stderr_cap: int,
) -> list[dict[str, Any]]:
    """Run task.setup commands through the same allowlisted bash pipeline.
    Returns a list of tool-call-record-shaped dicts. Caller decides whether
    to fail the run if any returned non-zero exit code / was rejected."""
    records: list[dict[str, Any]] = []
    for cmd in commands:
        rec = run_bash_command(
            cmd,
            allowed_argv0=allowed_argv0,
            writable_prefixes=writable_prefixes,
            timeout_s=timeout_s,
            cwd=cwd,
            env=env,
            stdout_cap=stdout_cap,
            stderr_cap=stderr_cap,
        )
        records.append(
            {
                "command": rec.command,
                "allowed": rec.allowed,
                "rejection_reason": rec.rejection_reason,
                "exit_code": rec.exit_code,
                "stdout": rec.stdout,
                "stderr": rec.stderr,
                "stdout_truncated": rec.stdout_truncated,
                "stderr_truncated": rec.stderr_truncated,
                "wall_clock_ms": rec.wall_clock_ms,
                "timed_out": rec.timed_out,
            }
        )
    return records


def run_one_trial(
    *,
    client: Any,
    model: str,
    task: dict[str, Any],
    arm: str,
    cli_readme_text: str | None,
    skill_bodies: dict[str, str],
    skill_index: list[tuple[str, str]],
    max_turns: int,
    timeout_s: int,
    allowed_argv0: list[str],
    writable_prefix_patterns: list[str],
    stdout_cap: int,
    stderr_cap: int,
    agent_max_tokens: int,
    trial_dir: Path,
    cwd: Path,
    fixtures_dir: Path | None,
    dry_run: bool,
) -> RunResult:
    """Execute one trial of one task under one arm."""
    system = build_system_prompt(
        arm,
        cli_readme_text=cli_readme_text,
        skill_index=skill_index if arm == "cli-skills" else None,
        timeout_s=timeout_s,
    )
    user_content = task["prompt"]
    # Tool set is arm-dependent: cli-only gets bash, cli-skills gets bash + load_skill.
    tools_for_arm: list[dict[str, Any]] = [BASH_TOOL_SCHEMA]
    if arm == "cli-skills":
        tools_for_arm.append(LOAD_SKILL_TOOL_SCHEMA)

    # Per-trial state dir — reset every run so nothing leaks between tasks.
    ctl_state_dir = trial_dir / "ctl-state"
    if ctl_state_dir.exists():
        shutil.rmtree(ctl_state_dir)
    ctl_state_dir.mkdir(parents=True, exist_ok=True)

    trial_env = os.environ.copy()
    trial_env["CTL_STATE_DIR"] = str(ctl_state_dir)
    trial_env["WORKDIR"] = str(trial_dir)
    if fixtures_dir is not None:
        trial_env["CTL_FIXTURES_DIR"] = str(fixtures_dir)

    # Expand writable prefixes against the trial env so $CTL_STATE_DIR and
    # $WORKDIR resolve to THIS trial's paths.
    writable_prefixes = _expand_writable_prefixes(writable_prefix_patterns, trial_env)

    started_at = datetime.now(timezone.utc).isoformat()
    transcript: dict[str, Any] = {
        "task_id": task.get("id"),
        "task_title": task.get("title", ""),
        "task_bucket": task.get("bucket", ""),
        "task_tags": task.get("tags", []),
        "arm": arm,
        "trial": int(trial_dir.name.split("_")[-1]) if trial_dir.name.startswith("trial_") else 0,
        "model": model,
        "started_at": started_at,
        "ended_at": None,
        "wall_clock_seconds": 0.0,
        "ctl_state_dir": str(ctl_state_dir),
        "workdir": str(trial_dir),
        "system_prompt": system,
        "user_prompt": user_content,
        "messages": [],
        "tool_calls": [],
        "setup_calls": [],
        "rejected_commands": [],
        "usage": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "total_calls": 0,
        },
        "final_text": "",
        "stop_reason": None,
        "api_errors": [],
        "dry_run": dry_run,
        "writable_prefixes_resolved": writable_prefixes,
        # Skill telemetry — populated only on the cli-skills arm. `skills_loaded`
        # records every successful load_skill call (in order, including
        # duplicates); `skill_load_calls` keeps the structured per-call log.
        "skills_loaded": [],
        "skill_load_calls": [],
    }

    # --- Setup commands (run once, NOT visible to the agent) ---
    setup_cmds = task.get("setup") or []
    setup_failed = False
    if setup_cmds:
        setup_records = _run_setup_commands(
            setup_cmds,
            allowed_argv0=allowed_argv0,
            writable_prefixes=writable_prefixes,
            timeout_s=timeout_s,
            cwd=cwd,
            env=trial_env,
            stdout_cap=stdout_cap,
            stderr_cap=stderr_cap,
        )
        transcript["setup_calls"] = setup_records
        for rec in setup_records:
            if not rec["allowed"] or rec["exit_code"] not in (0, None) or rec["timed_out"]:
                setup_failed = True
                break
        if setup_failed and not dry_run:
            transcript["stop_reason"] = "setup_failed"
            transcript["ended_at"] = datetime.now(timezone.utc).isoformat()
            return RunResult(
                transcript=transcript,
                copied_artifacts=[],
                setup_failed=True,
                error="setup command failed",
            )

    if dry_run:
        transcript["dry_run_payload"] = {
            "model": model,
            "temperature": 0,
            "system_chars": len(system),
            "tools": tools_for_arm,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        transcript["stop_reason"] = "dry_run"
        transcript["ended_at"] = datetime.now(timezone.utc).isoformat()
        return RunResult(transcript=transcript, copied_artifacts=[], setup_failed=False)

    # OpenAI Chat Completions wire format: system is a message, not a top-level
    # field. We keep the system message as the first entry in `api_messages`
    # (the one we send to the API each turn) and mirror the rest into
    # `transcript["messages"]` for downstream tooling.
    api_messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    transcript["messages"].append({"role": "user", "content": user_content})

    start_wall = time.monotonic()
    stop_reason: str | None = None

    for turn_idx in range(max_turns):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=agent_max_tokens,
                tools=tools_for_arm,
                tool_choice="auto",
                messages=api_messages,
            )
        except Exception as e:
            # Pull request id / status if the SDK exposes them.
            request_id = getattr(e, "request_id", None)
            status = getattr(e, "status_code", None)
            transcript["api_errors"].append(
                {
                    "turn": turn_idx,
                    "error_type": type(e).__name__,
                    "message": str(e),
                    "request_id": request_id,
                    "status_code": status,
                }
            )
            stop_reason = "api_error"
            break

        usage = getattr(resp, "usage", None)
        # OpenAI usage: prompt_tokens / completion_tokens / total_tokens.
        # We store them under the existing transcript keys so historical
        # tooling (score.py, judge.py) keeps working unchanged.
        in_tok = getattr(usage, "prompt_tokens", 0) or 0
        out_tok = getattr(usage, "completion_tokens", 0) or 0

        # Some OpenRouter providers surface cache stats under
        # prompt_tokens_details / completion_tokens_details. Read defensively —
        # absent fields stay at 0 (which is the pre-existing default anyway).
        cache_read = 0
        cache_create = 0
        ptd = getattr(usage, "prompt_tokens_details", None)
        if ptd is not None:
            cache_read = getattr(ptd, "cached_tokens", 0) or 0
        # `cache_creation_input_tokens` is an Anthropic-specific concept we
        # can't reliably read through the OpenAI-shaped usage object. Leave 0.

        u = transcript["usage"]
        u["input_tokens"] += in_tok
        u["output_tokens"] += out_tok
        u["cache_read_input_tokens"] += cache_read
        u["cache_creation_input_tokens"] += cache_create
        u["total_calls"] += 1

        choice = resp.choices[0] if getattr(resp, "choices", None) else None
        assistant_api_message = getattr(choice, "message", None)
        finish_reason = getattr(choice, "finish_reason", None) if choice else None

        # Build the Anthropic-shaped content blocks the transcript stores.
        assistant_blocks = (
            _assistant_blocks_from_openai_message(assistant_api_message)
            if assistant_api_message is not None
            else []
        )
        assistant_msg = {"role": "assistant", "content": assistant_blocks}
        transcript["messages"].append(assistant_msg)

        # Re-emit the assistant message to the API in OpenAI wire format so
        # the next turn's tool_call_ids resolve correctly. We must echo the
        # EXACT `tool_calls` payload back — the id values are what connect
        # the tool-result messages on the next request.
        api_tool_calls: list[dict[str, Any]] = []
        raw_tool_calls = (
            getattr(assistant_api_message, "tool_calls", None) or []
            if assistant_api_message is not None
            else []
        )
        for tc in raw_tool_calls:
            fn = getattr(tc, "function", None)
            api_tool_calls.append(
                {
                    "id": getattr(tc, "id", "") or "",
                    "type": "function",
                    "function": {
                        "name": getattr(fn, "name", "") if fn is not None else "",
                        "arguments": getattr(fn, "arguments", "") if fn is not None else "",
                    },
                }
            )
        assistant_text = (
            getattr(assistant_api_message, "content", None)
            if assistant_api_message is not None
            else None
        )
        api_assistant_entry: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_text,
        }
        if api_tool_calls:
            api_assistant_entry["tool_calls"] = api_tool_calls
        api_messages.append(api_assistant_entry)

        tool_use_blocks = [b for b in assistant_blocks if b.get("type") == "tool_use"]

        if not tool_use_blocks:
            stop_reason = _map_finish_reason(finish_reason) or "end_turn"
            break

        # Execute each tool call and append one OpenAI-shaped `tool` message
        # per call (that's how OpenAI pairs tool results with their ids).
        for tub in tool_use_blocks:
            name = tub.get("name")
            tu_input = tub.get("input", {}) or {}
            tu_id = tub.get("id")

            # ---- load_skill: only available on the cli-skills arm ----
            if name == "load_skill" and arm == "cli-skills":
                skill_name_raw = tu_input.get("name", "")
                skill_name = skill_name_raw if isinstance(skill_name_raw, str) else str(skill_name_raw)
                already_loaded = skill_name in transcript["skills_loaded"]
                if skill_name in skill_bodies:
                    body = skill_bodies[skill_name]
                    tool_result_body = body
                    is_error = False
                    found = True
                    transcript["skills_loaded"].append(skill_name)
                else:
                    found = False
                    is_error = True
                    available = sorted(skill_bodies.keys())
                    tool_result_body = json.dumps(
                        {
                            "error": "skill not found",
                            "name": skill_name,
                            "available": available,
                        }
                    )
                transcript["skill_load_calls"].append(
                    {
                        "turn": turn_idx,
                        "tool_use_id": tu_id,
                        "name": skill_name,
                        "found": found,
                        "duplicate": found and already_loaded,
                    }
                )
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tu_id,
                        "content": tool_result_body,
                    }
                )
                transcript["messages"].append(
                    {
                        "role": "tool",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tu_id,
                                "content": tool_result_body,
                                "is_error": is_error,
                            }
                        ],
                    }
                )
                continue

            if name != "bash":
                err_msg = f"unknown tool: {name!r}"
                tool_result_body = f"ERROR: {err_msg}"
                transcript["tool_calls"].append(
                    {
                        "turn": turn_idx,
                        "tool_use_id": tu_id,
                        "command": None,
                        "allowed": False,
                        "rejection_reason": err_msg,
                        "exit_code": None,
                        "stdout": "",
                        "stderr": "",
                        "stdout_truncated": False,
                        "stderr_truncated": False,
                        "wall_clock_ms": 0,
                        "timed_out": False,
                    }
                )
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tu_id,
                        "content": tool_result_body,
                    }
                )
                # Mirror into the transcript in the same content-block shape
                # previous arms/judge tooling already knows how to render.
                transcript["messages"].append(
                    {
                        "role": "tool",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tu_id,
                                "content": tool_result_body,
                                "is_error": True,
                            }
                        ],
                    }
                )
                continue

            command = tu_input.get("command", "")
            if not isinstance(command, str):
                command = str(command)

            record = run_bash_command(
                command,
                allowed_argv0=allowed_argv0,
                writable_prefixes=writable_prefixes,
                timeout_s=timeout_s,
                cwd=cwd,
                env=trial_env,
                stdout_cap=stdout_cap,
                stderr_cap=stderr_cap,
            )
            row = {
                "turn": turn_idx,
                "tool_use_id": tu_id,
                "command": record.command,
                "allowed": record.allowed,
                "rejection_reason": record.rejection_reason,
                "exit_code": record.exit_code,
                "stdout": record.stdout,
                "stderr": record.stderr,
                "stdout_truncated": record.stdout_truncated,
                "stderr_truncated": record.stderr_truncated,
                "wall_clock_ms": record.wall_clock_ms,
                "timed_out": record.timed_out,
            }
            transcript["tool_calls"].append(row)
            if not record.allowed:
                transcript["rejected_commands"].append(
                    {"command": record.command, "reason": record.rejection_reason}
                )

            tool_body = tool_result_for(record)
            api_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tu_id,
                    "content": tool_body,
                }
            )
            transcript["messages"].append(
                {
                    "role": "tool",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tu_id,
                            "content": tool_body,
                            "is_error": not record.allowed or record.timed_out,
                        }
                    ],
                }
            )

        # If the model returned a terminal finish_reason despite emitting tool
        # calls (rare on OpenAI but possible), break. Normal tool-use path
        # has finish_reason == "tool_calls" — keep looping.
        mapped = _map_finish_reason(finish_reason)
        if mapped and mapped not in ("tool_use", None):
            stop_reason = mapped
            break
    else:
        stop_reason = "max_turns"

    transcript["stop_reason"] = stop_reason or "end_turn"
    transcript["ended_at"] = datetime.now(timezone.utc).isoformat()
    transcript["wall_clock_seconds"] = round(time.monotonic() - start_wall, 3)
    transcript["final_text"] = _final_assistant_text(transcript["messages"])

    # --- Artifact copy-out: any /tmp/task-*.* mentioned in the prompt ---
    copied: list[str] = []
    for path_str in _extract_artifact_paths(user_content):
        src = Path(path_str)
        if not src.exists() or not src.is_file():
            continue
        ext = src.suffix.lstrip(".") or "bin"
        dst = trial_dir / f"artifact.{ext}"
        try:
            shutil.copy2(src, dst)
            copied.append(str(src))
        except Exception as e:
            transcript["api_errors"].append(
                {"turn": -1, "error_type": "ArtifactCopyError", "message": str(e)}
            )

    return RunResult(
        transcript=transcript,
        copied_artifacts=copied,
        setup_failed=False,
    )


# ---------------------------------------------------------------------------
# Task discovery
# ---------------------------------------------------------------------------


def find_task_file(task_id: str, tasks_dir: Path) -> Path:
    """Locate tasks/<id>-<slug>.yaml or tasks/<id>.yaml."""
    direct = tasks_dir / f"{task_id}.yaml"
    if direct.exists():
        return direct
    candidates = sorted(tasks_dir.glob(f"{task_id}-*.yaml"))
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise SystemExit(
            f"multiple task files match id {task_id!r}: {[c.name for c in candidates]}"
        )
    raise SystemExit(f"no task file found for id {task_id!r} in {tasks_dir}")


def load_task(path: Path) -> dict[str, Any]:
    """Load and lightly validate one task file against the new schema."""
    with open(path, "r", encoding="utf-8") as f:
        task = yaml.safe_load(f)
    if not isinstance(task, dict):
        raise SystemExit(f"task file {path} did not parse to a mapping")

    # YAML happily parses "042" as the int 42 if unquoted; normalize.
    if "id" in task and not isinstance(task["id"], str):
        task["id"] = str(task["id"]).zfill(3)

    for required in ("id", "prompt"):
        if required not in task:
            raise SystemExit(f"task {path} is missing required key {required!r}")

    # At least one of judge_rubric or rule_check must be present. Pure rule-
    # scored tasks don't need the judge at all; pure judge-scored tasks stay
    # valid as before. A task with neither is malformed.
    has_rubric = "judge_rubric" in task and task["judge_rubric"]
    has_rules = "rule_check" in task and task["rule_check"]
    if not has_rubric and not has_rules:
        raise SystemExit(
            f"task {path} must define at least one of `judge_rubric` or "
            f"`rule_check` (neither was present or both were empty)"
        )

    if "judge_rubric" in task and task["judge_rubric"] is not None:
        if not isinstance(task["judge_rubric"], list) or not task["judge_rubric"]:
            raise SystemExit(f"task {path} judge_rubric must be a non-empty list")
        for item in task["judge_rubric"]:
            for key in ("id", "criterion", "weight"):
                if key not in item:
                    raise SystemExit(
                        f"task {path} judge_rubric item missing required {key!r}: {item}"
                    )

    if "rule_check" in task and task["rule_check"] is not None:
        if not isinstance(task["rule_check"], list) or not task["rule_check"]:
            raise SystemExit(f"task {path} rule_check must be a non-empty list")
        allowed_asserts = {
            "tool_called",
            "no_tool_called",
            "tool_sequence",
            "final_text_regex",
            "final_text_contains",
            "exit_code_seen",
        }
        for item in task["rule_check"]:
            if not isinstance(item, dict):
                raise SystemExit(
                    f"task {path} rule_check entry must be a mapping: {item!r}"
                )
            for key in ("id", "assert", "weight"):
                if key not in item:
                    raise SystemExit(
                        f"task {path} rule_check item missing required {key!r}: {item}"
                    )
            if item["assert"] not in allowed_asserts:
                raise SystemExit(
                    f"task {path} rule_check item {item['id']!r} has unknown "
                    f"assert {item['assert']!r}; allowed: {sorted(allowed_asserts)}"
                )

    task.setdefault("title", "")
    task.setdefault("bucket", "")
    task.setdefault("tags", [])
    task.setdefault("judge_context", "")
    task.setdefault("setup", [])
    task.setdefault("judge_rubric", [])
    task.setdefault("rule_check", [])
    return task


def discover_all_tasks(tasks_dir: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for p in sorted(tasks_dir.glob("*.yaml")):
        tasks.append(load_task(p))
    # Sort by id so --all is deterministic even if the glob order changes.
    tasks.sort(key=lambda t: t["id"])
    return tasks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="run.py",
        description="Run CLI_VS_SKILLS tasks and record transcripts.",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--task", help="task id to run (e.g. 042 or 000)")
    g.add_argument("--all", action="store_true", help="run every task under tasks/")
    p.add_argument(
        "--arm",
        choices=["cli-only", "cli-skills", "both"],
        default="both",
        help="which arm(s) to run (default: both)",
    )
    p.add_argument("--trials", type=int, default=1, help="trials per (task, arm)")
    p.add_argument(
        "--out",
        default=None,
        help="output directory (default: results/<UTC-timestamp>/)",
    )
    p.add_argument("--model", default=None, help="override agent_model from config.yaml")
    p.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="override max_turns from config.yaml",
    )
    p.add_argument(
        "--only-bucket",
        default=None,
        help="only run tasks whose bucket matches (e.g. ambiguous)",
    )
    p.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"path to config.yaml (default: {DEFAULT_CONFIG_PATH})",
    )
    p.add_argument(
        "--tasks-dir",
        default=str(REPO_ROOT / "tasks"),
        help="tasks directory (default: <repo>/tasks)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the assembled system prompt and exit without hitting the API",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    cfg_path = Path(args.config).resolve()
    if not cfg_path.exists():
        print(f"config file not found: {cfg_path}", file=sys.stderr)
        return 2
    config = load_config(cfg_path)

    model = args.model or config.get("agent_model") or config.get("model")
    if not model:
        print("config.yaml must set agent_model", file=sys.stderr)
        return 2
    max_turns = int(args.max_turns or config.get("max_turns", 25))
    timeout_s = int(config.get("per_command_timeout_seconds", 30))
    allowed_argv0 = list(config.get("allowed_argv0", []))
    writable_prefix_patterns = list(config.get("writable_paths", ["/tmp/"]))
    stdout_cap = int(config.get("stdout_cap_bytes", 10240))
    stderr_cap = int(config.get("stderr_cap_bytes", 10240))
    agent_max_tokens = int(config.get("agent_max_tokens", 4096))

    tasks_dir = Path(args.tasks_dir).resolve()
    if not tasks_dir.exists():
        print(f"tasks dir does not exist: {tasks_dir}", file=sys.stderr)
        return 2

    if args.all:
        tasks = discover_all_tasks(tasks_dir)
        if not tasks:
            print(f"no *.yaml tasks found under {tasks_dir}", file=sys.stderr)
            return 2
    else:
        tasks = [load_task(find_task_file(args.task, tasks_dir))]

    if args.only_bucket:
        tasks = [t for t in tasks if t.get("bucket") == args.only_bucket]
        if not tasks:
            print(
                f"no tasks match bucket {args.only_bucket!r}", file=sys.stderr
            )
            return 2

    arms = ["cli-only", "cli-skills"] if args.arm == "both" else [args.arm]

    # Load documentation sources once.
    cli_readme_text = load_file_text(REPO_ROOT / "cli" / "README.md")

    # Skills now live as one .md per skill under skills_dir. Each file has a
    # YAML frontmatter block with `name` + `description`; the body is loaded
    # on-demand via the load_skill tool. The system prompt only carries the
    # index, not the bodies.
    skills_dir_cfg = config.get("skills_dir", "skills/")
    skills_dir = Path(skills_dir_cfg)
    if not skills_dir.is_absolute():
        skills_dir = REPO_ROOT / skills_dir

    # Backward-compat: warn loudly if the legacy monolithic SKILLS.md is still
    # around. We do NOT load it — the index/tool model is the only path.
    # Only relevant if we're actually going to use the skills directory.
    legacy_skills_md = skills_dir / "SKILLS.md"
    if "cli-skills" in arms and legacy_skills_md.exists():
        print(
            f"WARNING: deprecated {legacy_skills_md} is present and will be "
            "ignored. The harness now loads individual skill .md files with "
            "frontmatter. Delete SKILLS.md to silence this warning.",
            file=sys.stderr,
        )

    # Only validate / load skills when an arm that uses them is in scope.
    # A malformed skill file should not block the cli-only arm.
    skill_bodies: dict[str, str] = {}
    skill_index: list[tuple[str, str]] = []
    if "cli-skills" in arms:
        try:
            skill_bodies, skill_index = load_skill_index(skills_dir)
        except RuntimeError as e:
            print(f"failed to load skills from {skills_dir}: {e}", file=sys.stderr)
            return 2

        if not skill_index and not args.dry_run:
            print(
                f"no skills found under {skills_dir}; cannot run cli-skills arm.",
                file=sys.stderr,
            )
            return 2

    # For dry-run, inject a placeholder index so the prompt builder doesn't
    # raise while a parallel agent is still authoring the skill files.
    skill_index_effective = skill_index
    skill_bodies_effective = skill_bodies
    if args.dry_run and "cli-skills" in arms and not skill_index:
        skill_index_effective = [
            (
                "(no-skills-yet)",
                "Placeholder — no skill files were found in skills/ at dry-run time.",
            )
        ]
        skill_bodies_effective = {}

    # Resolve output dir.
    if args.out:
        out_root = Path(args.out).resolve()
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        default_root = Path(config.get("results_root", "results/"))
        if not default_root.is_absolute():
            default_root = REPO_ROOT / default_root
        out_root = default_root / ts
    out_root.mkdir(parents=True, exist_ok=True)

    # Lazy SDK import so --help and --dry-run work without the package.
    client = None
    if not args.dry_run:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            print(
                "OPENROUTER_API_KEY is not set; refusing to run "
                "(use --dry-run to exercise prompt assembly). "
                "Get a key at https://openrouter.ai/keys.",
                file=sys.stderr,
            )
            return 2
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as e:
            print(
                f"failed to import openai SDK: {e}. "
                "Install with: pip install -r harness/requirements.txt",
                file=sys.stderr,
            )
            return 2
        base_url = config.get("api_base_url", "https://openrouter.ai/api/v1")
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/cnnrobrien/CLI_VS_SKILLS",
                "X-Title": "CLI_VS_SKILLS benchmark",
            },
        )

    fixtures_dir = REPO_ROOT / "fixtures"
    if not fixtures_dir.exists():
        fixtures_dir = None  # CLI may fall back to its own default.

    # Self-describing manifest so results/... is interpretable standalone.
    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "agent_model": model,
        "api_base_url": config.get("api_base_url", "https://openrouter.ai/api/v1"),
        "max_turns": max_turns,
        "per_command_timeout_seconds": timeout_s,
        "allowed_argv0": allowed_argv0,
        "writable_prefix_patterns": writable_prefix_patterns,
        "arms": arms,
        "trials": args.trials,
        "dry_run": args.dry_run,
        "task_ids": [t["id"] for t in tasks],
        "only_bucket": args.only_bucket,
        "tasks_dir": str(tasks_dir),
        "config_path": str(cfg_path),
        "pinned_now": config.get("pinned_now"),
        "cli_readme_present": cli_readme_text is not None,
        "skills_dir": str(skills_dir),
        "skills_indexed": [name for name, _ in skill_index],
        "legacy_skills_md_present": legacy_skills_md.exists(),
    }
    with open(out_root / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    if args.dry_run:
        for arm in arms:
            sp = build_system_prompt(
                arm,
                cli_readme_text=cli_readme_text,
                skill_index=skill_index_effective if arm == "cli-skills" else None,
                timeout_s=timeout_s,
            )
            print(f"===== system prompt for arm={arm} =====")
            print(sp)
            print("===== end =====\n")
            for task in tasks:
                print(f"----- user prompt for task={task['id']} -----")
                print(task["prompt"])
                print("----- end -----\n")

    any_failures = False
    for task in tasks:
        for arm in arms:
            for trial in range(args.trials):
                trial_dir = out_root / str(task["id"]) / arm / f"trial_{trial}"
                trial_dir.mkdir(parents=True, exist_ok=True)

                result = run_one_trial(
                    client=client,
                    model=model,
                    task=task,
                    arm=arm,
                    cli_readme_text=cli_readme_text,
                    skill_bodies=skill_bodies_effective,
                    skill_index=skill_index_effective,
                    max_turns=max_turns,
                    timeout_s=timeout_s,
                    allowed_argv0=allowed_argv0,
                    writable_prefix_patterns=writable_prefix_patterns,
                    stdout_cap=stdout_cap,
                    stderr_cap=stderr_cap,
                    agent_max_tokens=agent_max_tokens,
                    trial_dir=trial_dir,
                    cwd=REPO_ROOT,
                    fixtures_dir=fixtures_dir,
                    dry_run=args.dry_run,
                )

                result.transcript["artifact_files_copied"] = result.copied_artifacts

                with open(trial_dir / "transcript.json", "w", encoding="utf-8") as f:
                    json.dump(result.transcript, f, indent=2, default=str)

                status = result.transcript.get("stop_reason", "unknown")
                tok = result.transcript["usage"]
                total_tokens = tok["input_tokens"] + tok["output_tokens"]
                n_calls = len(result.transcript["tool_calls"])
                n_rejected = len(result.transcript["rejected_commands"])
                print(
                    f"[task {task['id']} | arm {arm} | trial {trial}] "
                    f"stop={status} tool_calls={n_calls} rejected={n_rejected} "
                    f"tokens={total_tokens} artifacts={len(result.copied_artifacts)}"
                )
                if result.transcript.get("api_errors") or result.setup_failed:
                    any_failures = True

    print(f"\nresults written to: {out_root}")
    return 1 if any_failures else 0


if __name__ == "__main__":
    sys.exit(main())
