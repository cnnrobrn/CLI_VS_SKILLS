"""`ctl pipeline run|status <name>` subcommand."""
from __future__ import annotations

import os
import sys

from .common import (
    EXIT_OK,
    EXIT_REFUSED,
    EXIT_USER_ERROR,
    err,
    fixtures_dir,
    load_json,
    state_read,
    state_write,
)

HELP = """\
usage: ctl pipeline run <name> [--confirm] [--resume] [--rollback] [--verify]
       ctl pipeline status <name>

`run` executes the named pipeline; output is read from the fixture (no
real work is performed). `status` prints the last recorded state for
that pipeline (or `clean` if it has never run in this state dir).

Arguments:
  name              Pipeline name (e.g. deploy-prod, backfill-orders).

Options:
  --confirm         Pass through the `requires_confirm` gate.
  --resume          Continue a partially-applied pipeline from checkpoint.
  --rollback        Roll back the applied portion of a partial pipeline.
  --verify          Run an extra verification pass (pipelines that
                    support it will report discrepancies).
  -h, --help        Show this message and exit.

Exit codes:
  0    success (including safe no-ops like bare run in partial state)
  1    unknown pipeline / bad state
  2    refused (requires --confirm) or prerequisite unmet
"""


def _pipeline_path(name: str) -> str:
    """Resolve a pipeline fixture. Accepts either the friendly name
    (`deploy-prod`) or the id (`pipe-01`). The on-disk filename uses the
    name, but tasks and the task README reference ids interchangeably."""
    direct = os.path.join(fixtures_dir(), "pipelines", f"{name}.json")
    if os.path.exists(direct):
        return direct
    # Fall back: scan for matching id.
    pipes_dir = os.path.join(fixtures_dir(), "pipelines")
    if os.path.isdir(pipes_dir):
        for fn in os.listdir(pipes_dir):
            if not fn.endswith(".json"):
                continue
            try:
                pipe = load_json(os.path.join(pipes_dir, fn))
            except Exception:
                continue
            if pipe.get("id") == name or pipe.get("name") == name:
                return os.path.join(pipes_dir, fn)
    return direct  # returning a missing path; caller checks os.path.exists


def _emit_lines(lines: list[str], stream) -> None:
    for line in lines:
        stream.write(line.rstrip("\n") + "\n")


def _write_skipped_file(side_effects: dict | None) -> None:
    if not side_effects:
        return
    spec = side_effects.get("write_file")
    if not spec:
        return
    path = spec.get("path")
    content = spec.get("content", "")
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except OSError:
        # Writing /tmp on a read-only system is non-fatal for the CLI
        # contract; the stderr warning still goes out.
        pass


# ---------------------------------------------------------------------------
# `run` handler
# ---------------------------------------------------------------------------

def _run(name: str, confirm: bool, resume: bool, rollback: bool, verify: bool) -> int:
    path = _pipeline_path(name)
    if not os.path.exists(path):
        err("not found")
        return EXIT_USER_ERROR

    pipe = load_json(path)
    pid = pipe.get("id", name)

    # --- confirm gate ---
    if pipe.get("requires_confirm") and not confirm:
        err(pipe.get("refused_message", "refused"))
        return EXIT_REFUSED

    # --- prerequisite gate ---
    prereq = pipe.get("requires_prereq")
    if prereq:
        if state_read(f"{prereq}_ran.json") is None:
            err(pipe.get("prereq_failure_message", "prerequisite not met"))
            return EXIT_REFUSED

    # --- pipe-07 special-case state machine ---
    if pid == "pipe-07":
        return _run_pipe07(pipe, resume=resume, rollback=rollback)

    # --- pipe-09 --verify branch ---
    if pid == "pipe-09" and verify:
        vr = pipe.get("verify_result", {})
        _emit_lines(vr.get("lines", []), sys.stdout)
        return EXIT_OK

    # --- default run ---
    dr = pipe.get("default_run_result", {})
    _emit_lines(dr.get("lines", []), sys.stdout)
    _emit_lines(dr.get("stderr_lines", []), sys.stderr)
    _write_skipped_file(dr.get("side_effects"))

    # --- state side-effects ---
    # pipe-03 marks pages cache stale.
    if pipe.get("marks_cache_stale_after_run"):
        state_write("cache_stale.json", {"by": pid})
    # Track that this pipeline ran (supports prereq gating for pipe-05).
    state_write(f"{pid}_ran.json", {"name": name})

    # Search-index stale flag (set by pipe-07; see _run_pipe07).
    if dr.get("marks_search_index_stale"):
        state_write("search_index_stale.json", {"by": pid})

    status = dr.get("status", "ok")
    if status == "ok":
        return EXIT_OK
    err(dr.get("error", "pipeline failed"))
    return EXIT_USER_ERROR


def _run_pipe07(pipe: dict, resume: bool, rollback: bool) -> int:
    """Pipe-07 has a three-state life cycle backed by the state dir:

      clean   -> first `run` leaves it in `partial` (147/200), exit 0.
      partial -> bare `run` is a safe no-op: prints status to stdout,
                 informational message to stderr, exit 0.
                 `run --resume` moves it to `complete` (200/200).
                 `run --rollback` moves it to `rolled_back` (0/200).
      complete -> bare `run` is a no-op, exit 0.
      rolled_back -> bare `run` replays to partial state, exit 0.

    The default state reflected in the fixture on disk is the post-partial
    state, so `ctl pipeline status pipe-07` shows `partial: 147/200` even
    when the state dir is empty. Only after a real `--resume` or
    `--rollback` does the state move.
    """
    pid = "pipe-07"
    cur = state_read(f"{pid}_state.json") or {"state": "partial"}
    state = cur.get("state", "partial")
    name = pipe.get("name", pid)
    pfs = pipe.get("partial_failure_state", {})

    if rollback:
        rr = pipe.get("rollback_result", {})
        _emit_lines(rr.get("lines", []), sys.stdout)
        state_write(f"{pid}_state.json", {
            "state": "rolled_back",
            "completed": 0,
            "remaining": 200,
        })
        # Any pipe-07 action invalidates the search index (A6).
        state_write("search_index_stale.json", {"by": pid})
        return EXIT_OK

    if resume:
        if state in ("complete", "rolled_back"):
            err("nothing to resume")
            return EXIT_USER_ERROR
        rr = pipe.get("resume_result", {})
        _emit_lines(rr.get("lines", []), sys.stdout)
        state_write(f"{pid}_state.json", {
            "state": "complete",
            "completed": 200,
            "remaining": 0,
        })
        # Any pipe-07 action invalidates the search index (A6).
        state_write("search_index_stale.json", {"by": pid})
        return EXIT_OK

    # Bare run: handle based on current state.
    if state == "complete":
        # Already completed; bare re-run is a no-op.
        sys.stdout.write("pipeline already completed\n")
        return EXIT_OK

    if state == "rolled_back":
        # Rolled back; bare re-run replays to partial state (canonical post-run result).
        dr = pipe.get("default_run_result", {})
        _emit_lines(dr.get("lines", []), sys.stdout)
        _emit_lines(dr.get("stderr_lines", []), sys.stderr)
        if dr.get("marks_search_index_stale"):
            state_write("search_index_stale.json", {"by": pid})
        state_write(f"{pid}_state.json", {
            "state": "partial",
            "completed": 147,
            "remaining": 53,
        })
        return EXIT_OK

    # state == "partial": bare run is a safe no-op with status output.
    if state == "partial":
        # Retrieve current state values (may differ if state was persisted).
        completed = cur.get("completed", pfs.get("completed", 147))
        remaining = cur.get("remaining", pfs.get("remaining", 53))

        # Print informational message to stderr.
        err(
            f"{pid} already partially applied at {completed}/{completed + remaining}; "
            f"use --resume to continue or --rollback to revert"
        )

        # Print status summary to stdout (same as `ctl pipeline status pipe-07`).
        sys.stdout.write(
            f"pipeline: {name} ({pid})\n"
            f"completed: {completed}/{completed + remaining}, "
            f"remaining: {remaining}, state: partial\n"
        )
        if state == "partial":
            sys.stdout.write(
                f"failed_at: {pfs.get('failed_at', 'unknown')}\n"
                f"cause: {pfs.get('cause', 'unknown')}\n"
                f"collateral_refunds: {', '.join(pfs.get('collateral_refunds', []))}\n"
            )
        return EXIT_OK

    # (Clean state or other; unreachable with baked fixtures but kept for completeness.)
    dr = pipe.get("default_run_result", {})
    _emit_lines(dr.get("lines", []), sys.stdout)
    _emit_lines(dr.get("stderr_lines", []), sys.stderr)
    if dr.get("marks_search_index_stale"):
        state_write("search_index_stale.json", {"by": pid})
    state_write(f"{pid}_state.json", {
        "state": "partial",
        "completed": 147,
        "remaining": 53,
    })
    return EXIT_OK


# ---------------------------------------------------------------------------
# `status` handler
# ---------------------------------------------------------------------------

def _status(name: str) -> int:
    path = _pipeline_path(name)
    if not os.path.exists(path):
        err("not found")
        return EXIT_USER_ERROR
    pipe = load_json(path)
    pid = pipe.get("id", name)

    # pipe-07 has a rich partial-failure state to show.
    if pid == "pipe-07":
        pfs = pipe.get("partial_failure_state", {})
        cur = state_read(f"{pid}_state.json")
        if cur is None:
            # Default: the baked partial state from the fixture.
            completed = pfs.get("completed", 147)
            remaining = pfs.get("remaining", 53)
            state = pfs.get("state", "partial")
        else:
            completed = cur.get("completed", pfs.get("completed", 147))
            remaining = cur.get("remaining", pfs.get("remaining", 53))
            state = cur.get("state", "partial")

        sys.stdout.write(
            f"pipeline: {name} ({pid})\n"
            f"completed: {completed}/{completed + remaining}, "
            f"remaining: {remaining}, state: {state}\n"
        )
        if state == "partial":
            sys.stdout.write(
                f"failed_at: {pfs.get('failed_at', 'unknown')}\n"
                f"cause: {pfs.get('cause', 'unknown')}\n"
                f"collateral_refunds: {', '.join(pfs.get('collateral_refunds', []))}\n"
            )
        return EXIT_OK

    # Other pipelines: show whether they've run in this session.
    ran = state_read(f"{pid}_ran.json") is not None
    sys.stdout.write(
        f"pipeline: {name} ({pid})\n"
        f"ran_in_session: {'yes' if ran else 'no'}\n"
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def run(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    sub = argv[0]
    rest = argv[1:]

    if sub in ("-h", "--help"):
        sys.stdout.write(HELP)
        return EXIT_OK

    if sub == "run":
        if not rest or rest[0] in ("-h", "--help"):
            sys.stdout.write(HELP)
            return EXIT_OK
        name = rest[0]
        confirm = resume = rollback = verify = False
        i = 1
        while i < len(rest):
            a = rest[i]
            if a == "--confirm":
                confirm = True
            elif a == "--resume":
                resume = True
            elif a == "--rollback":
                rollback = True
            elif a == "--verify":
                verify = True
            elif a in ("-h", "--help"):
                sys.stdout.write(HELP)
                return EXIT_OK
            else:
                err(f"unknown argument: {a}")
                return EXIT_USER_ERROR
            i += 1
        return _run(name, confirm=confirm, resume=resume, rollback=rollback, verify=verify)

    if sub == "status":
        if not rest or rest[0] in ("-h", "--help"):
            sys.stdout.write(HELP)
            return EXIT_OK
        return _status(rest[0])

    err(f"unknown pipeline subcommand: {sub}")
    return EXIT_USER_ERROR
