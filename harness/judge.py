#!/usr/bin/env python3
"""CLI_VS_SKILLS LLM-as-judge scorer.

Walks a results directory, finds every transcript.json, redacts arm-identifying
strings, and asks an LLM judge (a *different* model family from the agent, via
OpenRouter) to grade the transcript against the task's rubric. Runs N judges
per transcript and takes a majority vote per rubric item.

Emits judgement.json next to each transcript. Run `harness/score.py` afterwards
to aggregate.

Usage:

    python harness/judge.py results/<ts>/ --judges 3
    python harness/judge.py results/<ts>/ --force   # re-judge existing results

See harness/README.md for context.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_DIR.parent
DEFAULT_CONFIG_PATH = HARNESS_DIR / "config.yaml"


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

# Arm-identifying substrings. We replace them with a neutral token so the
# judge can't learn from the label. Order matters: longer strings first so we
# don't chew half of them with a shorter match.
_ARM_MARKERS = [
    "cli-skills",
    "cli-only",
    "SKILLS.md",
    "skills/SKILLS.md",
    "Reference: SKILLS.md",
    "Reference: cli/README.md",
]


def _redact_string(s: str) -> str:
    if not s:
        return s
    out = s
    # Case-insensitive replace for each marker. Preserve reasonable spacing.
    for marker in _ARM_MARKERS:
        pattern = re.compile(re.escape(marker), flags=re.IGNORECASE)
        out = pattern.sub("[REDACTED-REFERENCE]", out)
    return out


def redact_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    """Deep-copy a transcript with arm-identifying strings scrubbed.

    We redact:
      * the top-level `arm` field (replaced with a neutral constant)
      * system_prompt (any mention of SKILLS.md / cli-skills / cli-only)
      * any text content in messages (agent-authored text or tool_result
        bodies — both can mention the arm if the agent read SKILLS.md).

    We preserve task_id and task_title (the task description is the same in
    both arms, so leaking it doesn't identify the arm).
    """
    t = copy.deepcopy(transcript)
    t["arm"] = "[REDACTED-ARM]"
    if isinstance(t.get("system_prompt"), str):
        t["system_prompt"] = _redact_string(t["system_prompt"])
    for msg in t.get("messages", []):
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = _redact_string(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and isinstance(block.get("text"), str):
                    block["text"] = _redact_string(block["text"])
                if block.get("type") == "tool_result" and isinstance(
                    block.get("content"), str
                ):
                    block["content"] = _redact_string(block["content"])
    # Also scrub tool_calls stdout/stderr — the CLI or cat could surface it.
    for call in t.get("tool_calls", []):
        if isinstance(call.get("stdout"), str):
            call["stdout"] = _redact_string(call["stdout"])
        if isinstance(call.get("stderr"), str):
            call["stderr"] = _redact_string(call["stderr"])
    if isinstance(t.get("final_text"), str):
        t["final_text"] = _redact_string(t["final_text"])
    return t


# ---------------------------------------------------------------------------
# Judge prompt assembly
# ---------------------------------------------------------------------------


JUDGE_SYSTEM_PROMPT = """You are an impartial evaluator grading a single transcript of an
autonomous agent that was given a CLI tool and a task to complete.

You will be shown:
  1. The task the agent was given.
  2. Ground-truth context that may not be visible in the transcript itself.
  3. The full transcript (system prompt, agent messages, tool calls, tool
     results, and the agent's final answer).
  4. A rubric with binary pass/fail criteria.

Your job:
  * Read the transcript carefully.
  * For each rubric item, decide pass (true) or fail (false).
  * Provide a one-sentence justification referencing specific evidence.
  * Do NOT reward effort, politeness, or writing style unless the rubric
    calls for it.
  * If the transcript is ambiguous on a criterion, lean toward fail.

Output FORMAT: a single JSON object, no prose before or after, matching:

  {
    "scores": [
      {"id": "<rubric item id>", "pass": true|false, "justification": "<1 sentence>"}
    ]
  }

If you output anything other than that JSON object, the run is wasted.
"""


def _format_messages_for_judge(messages: list[dict[str, Any]]) -> str:
    """Render the messages[] as compact human-readable text the judge can scan."""
    out: list[str] = []
    for i, msg in enumerate(messages):
        role = msg.get("role", "?")
        content = msg.get("content")
        out.append(f"--- message[{i}] role={role} ---")
        if isinstance(content, str):
            out.append(content)
        elif isinstance(content, list):
            for b in content:
                if not isinstance(b, dict):
                    out.append(repr(b))
                    continue
                btype = b.get("type")
                if btype == "text":
                    out.append(f"[text]\n{b.get('text', '')}")
                elif btype == "tool_use":
                    inp = b.get("input", {})
                    cmd = inp.get("command") if isinstance(inp, dict) else inp
                    out.append(f"[tool_use id={b.get('id')} name={b.get('name')}]\n{cmd}")
                elif btype == "tool_result":
                    body = b.get("content", "")
                    is_err = b.get("is_error", False)
                    out.append(
                        f"[tool_result id={b.get('tool_use_id')} is_error={is_err}]\n{body}"
                    )
                elif btype == "thinking":
                    out.append(f"[thinking]\n{b.get('thinking', '')}")
                else:
                    out.append(f"[{btype}]\n{json.dumps(b, default=str)}")
    return "\n".join(out)


def build_judge_user_message(
    *,
    task: dict[str, Any],
    transcript: dict[str, Any],
) -> str:
    rubric_lines = []
    for item in task["judge_rubric"]:
        rubric_lines.append(
            f"  - id: {item['id']}\n"
            f"    weight: {item['weight']}\n"
            f"    criterion: {item['criterion']}"
        )
    rubric_block = "\n".join(rubric_lines)

    rendered_messages = _format_messages_for_judge(transcript.get("messages", []))
    final_text = transcript.get("final_text") or "(no final text recorded)"
    stop_reason = transcript.get("stop_reason") or "unknown"

    parts = [
        "# TASK",
        f"title: {task.get('title', '')}",
        f"bucket: {task.get('bucket', '')}",
        "",
        "## user_prompt",
        task["prompt"].rstrip(),
        "",
        "# GROUND-TRUTH CONTEXT (for grading only — not visible to the agent)",
        (task.get("judge_context") or "(none provided)").rstrip(),
        "",
        "# RUBRIC",
        rubric_block,
        "",
        "# TRANSCRIPT",
        f"stop_reason: {stop_reason}",
        f"tool_calls: {len(transcript.get('tool_calls', []))}",
        "",
        "## system_prompt (redacted)",
        (transcript.get("system_prompt") or "").rstrip(),
        "",
        "## messages",
        rendered_messages,
        "",
        "## final_text",
        final_text,
        "",
        "# YOUR TASK",
        "Produce the JSON object specified in the system prompt. "
        "One entry per rubric id in the order given above.",
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_object(raw: str) -> dict[str, Any] | None:
    """Best-effort: find the first top-level JSON object in the judge's output."""
    if not raw:
        return None
    # Fast path: entire response is JSON.
    raw_s = raw.strip()
    try:
        return json.loads(raw_s)
    except Exception:
        pass
    # Fallback: greedy match then walk back until json.loads succeeds.
    m = _JSON_OBJECT_RE.search(raw_s)
    if not m:
        return None
    candidate = m.group(0)
    # Try progressively shorter suffixes if parse fails.
    for end in range(len(candidate), 0, -1):
        try:
            return json.loads(candidate[:end])
        except Exception:
            continue
    return None


def normalize_judge_scores(
    parsed: dict[str, Any] | None,
    rubric: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Turn a parsed judge output into a canonical list of per-item scores.

    Returns (scores, parse_error). On parse error, every rubric item is marked
    as fail with a placeholder justification.
    """
    if not parsed or "scores" not in parsed or not isinstance(parsed["scores"], list):
        return (
            [
                {
                    "id": item["id"],
                    "pass": False,
                    "justification": "parse_error: no scores array in judge output",
                }
                for item in rubric
            ],
            True,
        )

    by_id: dict[str, dict[str, Any]] = {}
    for entry in parsed["scores"]:
        if not isinstance(entry, dict):
            continue
        eid = entry.get("id")
        if not eid:
            continue
        by_id[str(eid)] = entry

    out: list[dict[str, Any]] = []
    saw_any = False
    for item in rubric:
        iid = item["id"]
        entry = by_id.get(iid)
        if entry is None:
            out.append(
                {
                    "id": iid,
                    "pass": False,
                    "justification": "parse_error: judge omitted this rubric item",
                }
            )
            continue
        saw_any = True
        passed = bool(entry.get("pass", False))
        just = entry.get("justification", "")
        if not isinstance(just, str):
            just = str(just)
        out.append({"id": iid, "pass": passed, "justification": just[:500]})
    return out, not saw_any


# ---------------------------------------------------------------------------
# Judge execution
# ---------------------------------------------------------------------------


def call_judge_once(
    *,
    client: Any,
    judge_model: str,
    system: str,
    user: str,
    max_tokens: int,
) -> tuple[str, dict[str, Any], str | None]:
    """Call the judge via OpenAI-compatible chat completions. Returns
    (raw_text, usage_dict, error_message).

    Usage is recorded under the same transcript keys the Anthropic-era
    harness emitted (`input_tokens` / `output_tokens`) so the aggregator and
    any historical scoring code keep working. Cache fields stay 0 unless
    OpenRouter surfaces them in `prompt_tokens_details.cached_tokens`.
    """
    try:
        resp = client.chat.completions.create(
            model=judge_model,
            temperature=0,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
    except Exception as e:
        return ("", {}, f"{type(e).__name__}: {e}")

    usage = getattr(resp, "usage", None)
    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0 if usage else 0
    completion_tokens = getattr(usage, "completion_tokens", 0) or 0 if usage else 0
    cache_read = 0
    ptd = getattr(usage, "prompt_tokens_details", None) if usage else None
    if ptd is not None:
        cache_read = getattr(ptd, "cached_tokens", 0) or 0
    u = {
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "cache_read_input_tokens": cache_read,
        "cache_creation_input_tokens": 0,
    }

    text = ""
    choice = resp.choices[0] if getattr(resp, "choices", None) else None
    if choice is not None:
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None) if message is not None else None
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            # Some gateways return content-block lists even for plain text.
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
            text = "\n".join(parts)
    return (text, u, None)


def judge_transcript(
    *,
    client: Any,
    judge_model: str,
    task: dict[str, Any],
    redacted_transcript: dict[str, Any],
    n_judges: int,
    max_tokens: int,
) -> dict[str, Any]:
    """Run the judge N times and compute a majority vote."""
    rubric = task["judge_rubric"]
    system = JUDGE_SYSTEM_PROMPT
    user = build_judge_user_message(task=task, transcript=redacted_transcript)

    runs: list[dict[str, Any]] = []
    for i in range(n_judges):
        raw, usage, err = call_judge_once(
            client=client,
            judge_model=judge_model,
            system=system,
            user=user,
            max_tokens=max_tokens,
        )
        parsed = None
        if not err:
            parsed = extract_json_object(raw)
        if not parsed and not err:
            # One retry on parse failure.
            raw2, usage2, err2 = call_judge_once(
                client=client,
                judge_model=judge_model,
                system=system,
                user=user
                + "\n\nIMPORTANT: Your previous response was not valid JSON. "
                "Respond with only the JSON object specified.",
                max_tokens=max_tokens,
            )
            if not err2:
                raw = raw2
                for k in usage:
                    usage[k] = usage.get(k, 0) + usage2.get(k, 0)
                parsed = extract_json_object(raw2)

        scores, parse_error = normalize_judge_scores(parsed, rubric)
        runs.append(
            {
                "run_index": i,
                "raw": raw,
                "parsed": parsed,
                "scores": scores,
                "parse_error": bool(parse_error or err),
                "error": err,
                "usage": usage,
            }
        )

    # Majority vote per rubric item.
    rubric_ids = [item["id"] for item in rubric]
    majority: dict[str, dict[str, Any]] = {}
    for rid in rubric_ids:
        votes: list[bool] = []
        justifications: list[str] = []
        for run in runs:
            for s in run["scores"]:
                if s["id"] == rid:
                    votes.append(bool(s["pass"]))
                    justifications.append(s["justification"])
                    break
        counts = Counter(votes)
        if not counts:
            majority_pass = False
            max_vote = 0
        else:
            max_vote = max(counts.values())
            # Ties (e.g. 1 pass / 1 fail) resolve to fail — conservative.
            majority_pass = counts.most_common(1)[0][0] and max_vote > (n_judges // 2)
            if counts[True] == counts[False] and True in counts:
                majority_pass = False
        agreement = (max_vote / n_judges) if n_judges else 0.0
        majority[rid] = {
            "pass": majority_pass,
            "agreement": round(agreement, 3),
            "votes_pass": counts.get(True, 0),
            "votes_fail": counts.get(False, 0),
            "justifications": justifications,
        }

    total_weight = sum(item["weight"] for item in rubric)
    passed_weight = sum(
        item["weight"] for item in rubric if majority[item["id"]]["pass"]
    )
    task_score = (passed_weight / total_weight) if total_weight else 0.0

    low_agreement_items = [
        rid
        for rid in rubric_ids
        if majority[rid]["agreement"] < (n_judges - 1) / n_judges
    ]

    return {
        "task_id": task["id"],
        "task_title": task.get("title", ""),
        "task_bucket": task.get("bucket", ""),
        "arm_label_seen_by_judge": redacted_transcript.get("arm"),
        "judge_model": judge_model,
        "n_judges": n_judges,
        "runs": runs,
        "majority": majority,
        "task_score": round(task_score, 4),
        "total_weight": total_weight,
        "passed_weight": passed_weight,
        "low_agreement_items": low_agreement_items,
        "any_parse_error": any(r["parse_error"] for r in runs),
        "judged_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def load_tasks_index(tasks_dir: Path) -> dict[str, dict[str, Any]]:
    """Map task id -> parsed task dict, for fast lookup."""
    from run import load_task  # same-directory import

    idx: dict[str, dict[str, Any]] = {}
    for p in sorted(tasks_dir.glob("*.yaml")):
        try:
            task = load_task(p)
        except SystemExit:
            # Ignore malformed tasks — the run harness will have flagged them.
            continue
        idx[task["id"]] = task
    return idx


def find_transcripts(results_dir: Path) -> list[Path]:
    return sorted(results_dir.rglob("transcript.json"))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="judge.py",
        description="Score CLI_VS_SKILLS transcripts with an LLM judge.",
    )
    p.add_argument("results_dir", help="directory previously written by run.py")
    p.add_argument(
        "--judges",
        type=int,
        default=None,
        help="number of judge runs per transcript (must be odd; default from config)",
    )
    p.add_argument(
        "--judge-model",
        default=None,
        help="override judge_model from config.yaml",
    )
    p.add_argument(
        "--redact",
        action="store_true",
        default=True,
        help="redact arm-identifying strings before showing the transcript "
        "to the judge (default: on)",
    )
    p.add_argument(
        "--no-redact",
        dest="redact",
        action="store_false",
        help="disable redaction (useful only for debugging)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="re-judge transcripts that already have judgement.json",
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
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    # Allow `from run import load_task` inside the driver.
    sys.path.insert(0, str(HARNESS_DIR))

    args = _parse_args(argv if argv is not None else sys.argv[1:])
    cfg_path = Path(args.config).resolve()
    if not cfg_path.exists():
        print(f"config file not found: {cfg_path}", file=sys.stderr)
        return 2
    with open(cfg_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    judge_model = args.judge_model or config.get("judge_model")
    if not judge_model:
        print("config.yaml must set judge_model", file=sys.stderr)
        return 2
    n_judges = int(args.judges or config.get("judges_per_transcript", 3))
    if n_judges < 1:
        print("--judges must be >= 1", file=sys.stderr)
        return 2
    if n_judges % 2 == 0:
        print(
            "warning: --judges is even; majority ties resolve to fail",
            file=sys.stderr,
        )
    judge_max_tokens = int(config.get("judge_max_tokens", 2048))

    results_dir = Path(args.results_dir).resolve()
    if not results_dir.exists():
        print(f"results dir does not exist: {results_dir}", file=sys.stderr)
        return 2

    tasks_dir = Path(args.tasks_dir).resolve()
    if not tasks_dir.exists():
        print(f"tasks dir does not exist: {tasks_dir}", file=sys.stderr)
        return 2

    tasks_index = load_tasks_index(tasks_dir)
    transcripts = find_transcripts(results_dir)
    if not transcripts:
        print(f"no transcript.json files found under {results_dir}", file=sys.stderr)
        return 2

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            "OPENROUTER_API_KEY is not set; refusing to run. "
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

    judged = 0
    skipped = 0
    skipped_no_rubric = 0
    errors = 0
    t0 = time.monotonic()
    for tp in transcripts:
        judgement_path = tp.with_name("judgement.json")
        if judgement_path.exists() and not args.force:
            skipped += 1
            continue
        with open(tp, "r", encoding="utf-8") as f:
            transcript = json.load(f)

        task_id = transcript.get("task_id")
        task = tasks_index.get(str(task_id))
        if task is None:
            print(
                f"[skip] no task loaded for id={task_id!r} (transcript={tp})",
                file=sys.stderr,
            )
            errors += 1
            continue

        # Pure rule-scored tasks don't have a judge_rubric; for those we
        # emit a placeholder judgement.json so score.py knows the judge was
        # intentionally skipped (vs. never run). No API call is made.
        rubric = task.get("judge_rubric") or []
        if not rubric:
            placeholder = {
                "task_id": task_id,
                "task_title": task.get("title", ""),
                "task_bucket": task.get("bucket", ""),
                "arm_label_seen_by_judge": None,
                "judge_model": judge_model,
                "n_judges": 0,
                "runs": [],
                "majority": {},
                "task_score": None,
                "total_weight": 0,
                "passed_weight": 0,
                "low_agreement_items": [],
                "any_parse_error": False,
                "judged_at": datetime.now(timezone.utc).isoformat(),
                "judge_skipped": True,
                "judge_skipped_reason": "no judge_rubric in task",
                "arm": transcript.get("arm"),
                "trial": transcript.get("trial", 0),
                "transcript_path": str(tp.relative_to(results_dir)),
            }
            with open(judgement_path, "w", encoding="utf-8") as f:
                json.dump(placeholder, f, indent=2, default=str)
            skipped_no_rubric += 1
            print(
                f"[no-rubric] task={task_id} arm={transcript.get('arm')} "
                f"(rule-only task — judge not called)"
            )
            continue

        working = redact_transcript(transcript) if args.redact else copy.deepcopy(
            transcript
        )
        judgement = judge_transcript(
            client=client,
            judge_model=judge_model,
            task=task,
            redacted_transcript=working,
            n_judges=n_judges,
            max_tokens=judge_max_tokens,
        )
        # Preserve the original arm label ONLY in the output file — useful for
        # scoring. The judge itself never saw it.
        judgement["arm"] = transcript.get("arm")
        judgement["trial"] = transcript.get("trial", 0)
        judgement["transcript_path"] = str(tp.relative_to(results_dir))
        judgement["judge_skipped"] = False

        with open(judgement_path, "w", encoding="utf-8") as f:
            json.dump(judgement, f, indent=2, default=str)

        judged += 1
        print(
            f"[judged] task={task_id} arm={transcript.get('arm')} "
            f"score={judgement['task_score']:.3f} "
            f"low_agreement={len(judgement['low_agreement_items'])} "
            f"parse_errors={int(judgement['any_parse_error'])}"
        )

    dt = time.monotonic() - t0
    print(
        f"\njudged={judged} skipped={skipped} "
        f"no_rubric={skipped_no_rubric} errors={errors} "
        f"in {dt:.1f}s (use --force to re-judge)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
