#!/usr/bin/env python3
"""CLI_VS_SKILLS scoring aggregator.

Walks a results directory, collects all judgement.json files next to their
transcript.json siblings, and emits:

  * <results_dir>/scores.json   — machine-readable totals per arm, per bucket,
                                   per task.
  * <results_dir>/report.md     — a single readable markdown report.

Bootstrap 95% CIs are computed with 10,000 resamples over the task pool.

Usage:

    python harness/score.py results/<ts>/
    python harness/score.py results/<ts>/ --report /tmp/report.md

"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


HARNESS_DIR = Path(__file__).resolve().parent
REPO_ROOT = HARNESS_DIR.parent
DEFAULT_CONFIG_PATH = HARNESS_DIR / "config.yaml"


# ---------------------------------------------------------------------------
# Task index (needed so we can find rule_check blocks and run rule scoring
# inline when collecting records)
# ---------------------------------------------------------------------------


def _load_tasks_index(tasks_dir: Path) -> dict[str, dict[str, Any]]:
    """Map task id -> parsed task dict.

    We re-use run.load_task so validation stays consistent with what the
    runner accepted. Tasks that fail to load are just skipped (they can't
    appear in transcripts either).
    """
    sys.path.insert(0, str(HARNESS_DIR))
    from run import load_task  # same-directory import

    idx: dict[str, dict[str, Any]] = {}
    for p in sorted(tasks_dir.glob("*.yaml")):
        try:
            task = load_task(p)
        except SystemExit:
            continue
        idx[str(task["id"])] = task
    return idx


def _combined_task_score(
    rule_total: int,
    rule_passed: int,
    judge_total: int,
    judge_passed: int,
    judge_skipped: bool,
) -> tuple[float | None, str]:
    """Combine rule + judge weights into a single task_score.

    Scoring combination:
      * both present    -> (rule_passed + judge_passed) / (rule_total + judge_total)
      * rule only       -> rule_passed / rule_total
      * judge only      -> judge_passed / judge_total
      * neither usable  -> None (should not happen; task validation forbids it)

    ``scoring_mode`` is returned for reporting: "rule", "judge", or "hybrid".
    """
    has_rule = rule_total > 0
    # judge_skipped means the task declared no judge_rubric; treat it as absent.
    has_judge = judge_total > 0 and not judge_skipped

    if has_rule and has_judge:
        denom = rule_total + judge_total
        numer = rule_passed + judge_passed
        return (numer / denom if denom else 0.0, "hybrid")
    if has_rule:
        return (rule_passed / rule_total if rule_total else 0.0, "rule")
    if has_judge:
        return (judge_passed / judge_total if judge_total else 0.0, "judge")
    return (None, "none")


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def collect_records(
    results_dir: Path,
    *,
    tasks_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build one flat record per (task, arm, trial) with judgement + transcript
    signals we need for reporting.

    For every transcript we:
      1. Load the matching task (for `rule_check` block).
      2. Run rule evaluation inline if the task has rules.
      3. Read any existing judgement.json and pull the judge sub-score.
      4. Combine the two into the final `task_score` used for bucket means.
    """
    # Lazy import so score.py --help keeps working even if rules.py breaks.
    sys.path.insert(0, str(HARNESS_DIR))
    from rules import evaluate_rule_check

    records: list[dict[str, Any]] = []
    # Walk transcripts — judgement.json may be absent for pure rule tasks if
    # judge.py wasn't run yet, but we can still score them.
    for t_path in sorted(results_dir.rglob("transcript.json")):
        try:
            with open(t_path, "r", encoding="utf-8") as f:
                transcript = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"[skip] {t_path}: {e}", file=sys.stderr)
            continue

        j_path = t_path.with_name("judgement.json")
        judgement: dict[str, Any] | None = None
        if j_path.exists():
            try:
                with open(j_path, "r", encoding="utf-8") as f:
                    judgement = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                print(f"[warn] failed to load {j_path}: {e}", file=sys.stderr)
                judgement = None

        task_id = str(transcript.get("task_id") or (judgement or {}).get("task_id"))
        task = tasks_index.get(task_id)

        # Rule evaluation (inline, no API).
        rule_items = (task or {}).get("rule_check") or []
        rule_result: dict[str, Any] = {"items": [], "total_weight": 0, "passed_weight": 0}
        if rule_items:
            rule_result = evaluate_rule_check(rule_items, transcript)

        # Judge sub-score (from judgement.json if present).
        judge_skipped = bool((judgement or {}).get("judge_skipped", False))
        judge_total = int((judgement or {}).get("total_weight", 0) or 0)
        judge_passed = int((judgement or {}).get("passed_weight", 0) or 0)

        combined, scoring_mode = _combined_task_score(
            rule_total=rule_result["total_weight"],
            rule_passed=rule_result["passed_weight"],
            judge_total=judge_total,
            judge_passed=judge_passed,
            judge_skipped=judge_skipped,
        )

        # Sub-scores (fractional) for the per-task report breakdown.
        rule_score = (
            rule_result["passed_weight"] / rule_result["total_weight"]
            if rule_result["total_weight"]
            else None
        )
        judge_score = (
            judge_passed / judge_total
            if judge_total and not judge_skipped
            else None
        )

        usage = transcript.get("usage", {}) or {}
        rec = {
            "task_id": task_id,
            "task_title": transcript.get("task_title")
            or (judgement or {}).get("task_title", ""),
            "bucket": transcript.get("task_bucket")
            or (judgement or {}).get("task_bucket", ""),
            "arm": transcript.get("arm") or (judgement or {}).get("arm"),
            "trial": transcript.get("trial", (judgement or {}).get("trial", 0)),
            "task_score": float(combined) if combined is not None else 0.0,
            "has_combined_score": combined is not None,
            "scoring_mode": scoring_mode,  # "rule" | "judge" | "hybrid" | "none"
            "rule_score": rule_score,
            "judge_score": judge_score,
            "rule_items": rule_result["items"],
            "rule_total_weight": rule_result["total_weight"],
            "rule_passed_weight": rule_result["passed_weight"],
            "judge_total_weight": judge_total if not judge_skipped else 0,
            "judge_passed_weight": judge_passed if not judge_skipped else 0,
            "judge_skipped": judge_skipped,
            "low_agreement_items": list((judgement or {}).get("low_agreement_items", [])),
            "any_parse_error": bool((judgement or {}).get("any_parse_error", False)),
            "majority": (judgement or {}).get("majority", {}),
            "input_tokens": int(usage.get("input_tokens", 0)),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "tool_calls": len(transcript.get("tool_calls", []) or []),
            "rejected_calls": len(transcript.get("rejected_commands", []) or []),
            "wall_clock_seconds": float(transcript.get("wall_clock_seconds", 0.0)),
            "stop_reason": transcript.get("stop_reason"),
            "transcript_path": str(t_path.relative_to(results_dir)),
            "judgement_path": (
                str(j_path.relative_to(results_dir)) if j_path.exists() else None
            ),
        }
        records.append(rec)
    return records


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _median(xs: list[float]) -> float:
    return statistics.median(xs) if xs else 0.0


def bootstrap_mean_ci(
    values: list[float],
    *,
    n_resamples: int = 10000,
    seed: int = 20260424,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Return (mean, lower, upper) for a 1-alpha CI on the mean via bootstrap."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    lo_idx = max(int(n_resamples * (alpha / 2)), 0)
    hi_idx = min(int(n_resamples * (1 - alpha / 2)) - 1, n_resamples - 1)
    return (_mean(values), means[lo_idx], means[hi_idx])


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate(
    records: list[dict[str, Any]],
    *,
    low_agreement_threshold: float,
) -> dict[str, Any]:
    per_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        per_arm[r["arm"]].append(r)

    # Collapse trials to per-task-per-arm by averaging the task_score. Also
    # keep raw trial scores so we can report a median number of trials per
    # task at the end.
    per_task_arm_scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    per_task_arm_efficiency: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    task_titles: dict[str, str] = {}
    task_buckets: dict[str, str] = {}

    # Keep per-task rule / judge sub-scores for the per-task breakdown table,
    # and track each task's scoring mode once (it's fixed by the task YAML so
    # all trials share the same mode).
    per_task_arm_rule_scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    per_task_arm_judge_scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    task_scoring_modes: dict[str, str] = {}

    for r in records:
        key = (r["task_id"], r["arm"])
        per_task_arm_scores[key].append(r["task_score"])
        if r.get("rule_score") is not None:
            per_task_arm_rule_scores[key].append(float(r["rule_score"]))
        if r.get("judge_score") is not None:
            per_task_arm_judge_scores[key].append(float(r["judge_score"]))
        eff = per_task_arm_efficiency[key]
        eff["tokens"].append(r["input_tokens"] + r["output_tokens"])
        eff["tool_calls"].append(float(r["tool_calls"]))
        eff["wall_clock"].append(r["wall_clock_seconds"])
        eff["rejected"].append(float(r["rejected_calls"]))
        task_titles[r["task_id"]] = r["task_title"]
        task_buckets[r["task_id"]] = r["bucket"]
        # "none" only happens if the task is malformed — overwrite if any
        # trial records a real mode so we don't stick with "none" forever.
        if task_scoring_modes.get(r["task_id"]) in (None, "none"):
            task_scoring_modes[r["task_id"]] = r.get("scoring_mode", "none")

    # Per-arm headline.
    arms_summary: dict[str, Any] = {}
    for arm, arm_records in per_arm.items():
        task_means = []
        for tid in sorted({r["task_id"] for r in arm_records}):
            scores = per_task_arm_scores[(tid, arm)]
            if scores:
                task_means.append(_mean(scores))
        mean, lo, hi = bootstrap_mean_ci(task_means)
        tokens = [r["input_tokens"] + r["output_tokens"] for r in arm_records]
        calls = [r["tool_calls"] for r in arm_records]
        wall = [r["wall_clock_seconds"] for r in arm_records]
        rejected = [r["rejected_calls"] for r in arm_records]
        arms_summary[arm] = {
            "n_tasks": len({r["task_id"] for r in arm_records}),
            "n_trials": len(arm_records),
            "mean_task_score": round(mean, 4),
            "ci_low": round(lo, 4),
            "ci_high": round(hi, 4),
            "mean_tokens": round(_mean(tokens), 1),
            "median_tokens": round(_median(tokens), 1),
            "mean_tool_calls": round(_mean(calls), 2),
            "median_tool_calls": round(_median(calls), 2),
            "mean_wall_clock_seconds": round(_mean(wall), 2),
            "median_wall_clock_seconds": round(_median(wall), 2),
            "total_rejected_commands": int(sum(rejected)),
        }

    # Per-bucket.
    per_bucket: dict[str, dict[str, Any]] = defaultdict(dict)
    for arm, arm_records in per_arm.items():
        by_bucket: dict[str, list[float]] = defaultdict(list)
        for tid in sorted({r["task_id"] for r in arm_records}):
            bucket = task_buckets.get(tid, "")
            scores = per_task_arm_scores[(tid, arm)]
            if scores:
                by_bucket[bucket].append(_mean(scores))
        for bucket, tmeans in by_bucket.items():
            mean, lo, hi = bootstrap_mean_ci(tmeans)
            per_bucket[bucket][arm] = {
                "n_tasks": len(tmeans),
                "mean": round(mean, 4),
                "ci_low": round(lo, 4),
                "ci_high": round(hi, 4),
            }

    # Per-task deltas. We want (arm A = cli-only) vs (arm B = cli-skills).
    # If a task is only in one arm, delta is None.
    task_rows: list[dict[str, Any]] = []
    all_tids = sorted({r["task_id"] for r in records})
    for tid in all_tids:
        a_scores = per_task_arm_scores.get((tid, "cli-only"), [])
        b_scores = per_task_arm_scores.get((tid, "cli-skills"), [])
        a_mean = _mean(a_scores) if a_scores else None
        b_mean = _mean(b_scores) if b_scores else None
        delta = None
        if a_mean is not None and b_mean is not None:
            delta = round(b_mean - a_mean, 4)

        # Minimum judge agreement across rubric items, across all trials for
        # this task, across both arms we have.
        mins: list[float] = []
        for arm in ("cli-only", "cli-skills"):
            for r in records:
                if r["task_id"] != tid or r["arm"] != arm:
                    continue
                for info in r["majority"].values():
                    if isinstance(info, dict) and "agreement" in info:
                        mins.append(float(info["agreement"]))
        min_agreement = min(mins) if mins else None

        # Per-task sub-score breakdown, averaged across trials per arm.
        def _avg(seq: list[float]) -> float | None:
            return round(_mean(seq), 4) if seq else None

        sub_scores = {
            "cli-only": {
                "rule": _avg(per_task_arm_rule_scores.get((tid, "cli-only"), [])),
                "judge": _avg(per_task_arm_judge_scores.get((tid, "cli-only"), [])),
            },
            "cli-skills": {
                "rule": _avg(per_task_arm_rule_scores.get((tid, "cli-skills"), [])),
                "judge": _avg(per_task_arm_judge_scores.get((tid, "cli-skills"), [])),
            },
        }

        task_rows.append(
            {
                "task_id": tid,
                "title": task_titles.get(tid, ""),
                "bucket": task_buckets.get(tid, ""),
                "cli_only_score": round(a_mean, 4) if a_mean is not None else None,
                "cli_skills_score": round(b_mean, 4) if b_mean is not None else None,
                "delta": delta,
                "min_agreement": round(min_agreement, 3)
                if min_agreement is not None
                else None,
                "scoring_mode": task_scoring_modes.get(tid, "none"),
                "sub_scores": sub_scores,
            }
        )

    # Sort by delta descending, Nones at the bottom.
    task_rows.sort(
        key=lambda r: (r["delta"] is None, -(r["delta"] or 0.0), r["task_id"])
    )

    # Low-agreement flags: any task*arm with any item below threshold.
    low_agreement: list[dict[str, Any]] = []
    for r in records:
        flagged = [
            rid
            for rid, info in r["majority"].items()
            if isinstance(info, dict)
            and info.get("agreement", 1.0) < low_agreement_threshold
        ]
        if flagged:
            low_agreement.append(
                {
                    "task_id": r["task_id"],
                    "arm": r["arm"],
                    "trial": r["trial"],
                    "flagged_items": flagged,
                    "task_score": r["task_score"],
                }
            )

    # Rejected-command diagnostic.
    rejections_by_arm: dict[str, int] = defaultdict(int)
    for r in records:
        rejections_by_arm[r["arm"]] += r["rejected_calls"]

    # Count rule-only / judge-only / hybrid tasks for the summary section.
    # Count each task once (modes are a property of the task, not the trial).
    scoring_mode_counts = {"rule": 0, "judge": 0, "hybrid": 0, "none": 0}
    for mode in task_scoring_modes.values():
        scoring_mode_counts[mode] = scoring_mode_counts.get(mode, 0) + 1

    return {
        "n_trials": len(records),
        "arms": arms_summary,
        "per_bucket": per_bucket,
        "task_rows": task_rows,
        "low_agreement": low_agreement,
        "rejections_by_arm": dict(rejections_by_arm),
        "low_agreement_threshold": low_agreement_threshold,
        "scoring_mode_counts": scoring_mode_counts,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _fmt_score(s: float | None) -> str:
    return "—" if s is None else f"{s:.3f}"


def _fmt_delta(d: float | None) -> str:
    if d is None:
        return "—"
    sign = "+" if d > 0 else ""
    return f"{sign}{d:.3f}"


def render_markdown(agg: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# CLI_VS_SKILLS report\n")
    lines.append(f"Total trials judged: **{agg['n_trials']}**\n")

    # Scoring-mode summary (tasks, not trials).
    modes = agg.get("scoring_mode_counts") or {}
    if modes:
        lines.append("## Scoring mode breakdown\n")
        lines.append("| Mode | Tasks |")
        lines.append("|---|---:|")
        for key in ("rule", "judge", "hybrid", "none"):
            count = modes.get(key, 0)
            if count or key != "none":
                lines.append(f"| {key} | {count} |")
        lines.append("")

    # Headline.
    lines.append("## Headline\n")
    lines.append("| Arm | Tasks | Trials | Mean score | 95% CI |")
    lines.append("|---|---:|---:|---:|:---|")
    for arm in ("cli-only", "cli-skills"):
        s = agg["arms"].get(arm)
        if not s:
            continue
        lines.append(
            f"| `{arm}` | {s['n_tasks']} | {s['n_trials']} | "
            f"{s['mean_task_score']:.3f} | "
            f"[{s['ci_low']:.3f}, {s['ci_high']:.3f}] |"
        )
    # Arm-A vs arm-B delta if both exist.
    if "cli-only" in agg["arms"] and "cli-skills" in agg["arms"]:
        d = (
            agg["arms"]["cli-skills"]["mean_task_score"]
            - agg["arms"]["cli-only"]["mean_task_score"]
        )
        lines.append("")
        lines.append(f"**Headline delta (cli-skills − cli-only): {d:+.3f}**")
    lines.append("")

    # Per-bucket.
    lines.append("## Per-bucket scores\n")
    if not agg["per_bucket"]:
        lines.append("_no data_\n")
    else:
        lines.append("| Bucket | Arm | N | Mean | 95% CI |")
        lines.append("|---|---|---:|---:|:---|")
        for bucket in sorted(agg["per_bucket"].keys()):
            for arm in ("cli-only", "cli-skills"):
                s = agg["per_bucket"][bucket].get(arm)
                if not s:
                    continue
                lines.append(
                    f"| {bucket or '(none)'} | `{arm}` | {s['n_tasks']} | "
                    f"{s['mean']:.3f} | [{s['ci_low']:.3f}, {s['ci_high']:.3f}] |"
                )
        lines.append("")

    # Per-task delta.
    lines.append("## Per-task deltas (sorted by cli-skills − cli-only)\n")
    lines.append(
        "| Task | Title | Bucket | Mode | cli-only | cli-skills | Δ | "
        "judge_agreement_min |"
    )
    lines.append("|---|---|---|---|---:|---:|---:|---:|")
    for r in agg["task_rows"]:
        lines.append(
            f"| {r['task_id']} | {r['title']} | {r['bucket']} | "
            f"{r.get('scoring_mode', '—')} | "
            f"{_fmt_score(r['cli_only_score'])} | "
            f"{_fmt_score(r['cli_skills_score'])} | "
            f"{_fmt_delta(r['delta'])} | "
            f"{r['min_agreement'] if r['min_agreement'] is not None else '—'} |"
        )
    lines.append("")

    # Per-task rule / judge / combined sub-score breakdown. This only
    # meaningfully differs from the table above for hybrid tasks, but we
    # render all tasks here so the reader can see which sub-score drove the
    # combined number.
    lines.append("## Per-task rule / judge / combined breakdown\n")
    lines.append(
        "| Task | Mode | Arm | rule_score | judge_score | combined |"
    )
    lines.append("|---|---|---|---:|---:|---:|")
    for r in agg["task_rows"]:
        mode = r.get("scoring_mode", "none")
        sub = r.get("sub_scores") or {}
        for arm, combined_key in (
            ("cli-only", "cli_only_score"),
            ("cli-skills", "cli_skills_score"),
        ):
            arm_sub = sub.get(arm) or {}
            combined = r.get(combined_key)
            # Skip arms we have no data for at all.
            if (
                arm_sub.get("rule") is None
                and arm_sub.get("judge") is None
                and combined is None
            ):
                continue
            lines.append(
                f"| {r['task_id']} | {mode} | `{arm}` | "
                f"{_fmt_score(arm_sub.get('rule'))} | "
                f"{_fmt_score(arm_sub.get('judge'))} | "
                f"{_fmt_score(combined)} |"
            )
    lines.append("")

    # Top-10 wins / non-wins.
    scored = [r for r in agg["task_rows"] if r["delta"] is not None]
    top_b = sorted(scored, key=lambda r: (-r["delta"], r["task_id"]))[:10]
    top_a = sorted(scored, key=lambda r: (r["delta"], r["task_id"]))[:10]

    lines.append("## Top 10 tasks where cli-skills beat cli-only\n")
    if not top_b:
        lines.append("_no data_\n")
    else:
        lines.append("| Task | Title | Δ |")
        lines.append("|---|---|---:|")
        for r in top_b:
            lines.append(f"| {r['task_id']} | {r['title']} | {_fmt_delta(r['delta'])} |")
        lines.append("")

    lines.append("## Top 10 tasks where cli-only matched or beat cli-skills\n")
    if not top_a:
        lines.append("_no data_\n")
    else:
        lines.append("| Task | Title | Δ |")
        lines.append("|---|---|---:|")
        for r in top_a:
            lines.append(f"| {r['task_id']} | {r['title']} | {_fmt_delta(r['delta'])} |")
        lines.append("")

    # Low-agreement.
    lines.append(
        f"## Low inter-judge agreement (threshold < {agg['low_agreement_threshold']})\n"
    )
    if not agg["low_agreement"]:
        lines.append("_no rubric items fell below the threshold_\n")
    else:
        lines.append("| Task | Arm | Trial | Flagged items | Task score |")
        lines.append("|---|---|---:|---|---:|")
        for la in agg["low_agreement"]:
            lines.append(
                f"| {la['task_id']} | `{la['arm']}` | {la['trial']} | "
                f"{', '.join(la['flagged_items'])} | {la['task_score']:.3f} |"
            )
        lines.append("")

    # Efficiency.
    lines.append("## Efficiency (secondary signals)\n")
    lines.append(
        "| Arm | Mean tokens | Median tokens | Mean calls | Median calls | "
        "Mean wall-s | Median wall-s |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for arm in ("cli-only", "cli-skills"):
        s = agg["arms"].get(arm)
        if not s:
            continue
        lines.append(
            f"| `{arm}` | {s['mean_tokens']} | {s['median_tokens']} | "
            f"{s['mean_tool_calls']} | {s['median_tool_calls']} | "
            f"{s['mean_wall_clock_seconds']} | {s['median_wall_clock_seconds']} |"
        )
    lines.append("")

    # Diagnostics.
    lines.append("## Diagnostics\n")
    lines.append("### Rejected commands per arm (agent tried things outside the allowlist)\n")
    if not agg["rejections_by_arm"]:
        lines.append("_none_\n")
    else:
        lines.append("| Arm | Total rejections |")
        lines.append("|---|---:|")
        for arm, n in agg["rejections_by_arm"].items():
            lines.append(f"| `{arm}` | {n} |")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="score.py",
        description="Aggregate CLI_VS_SKILLS judgements into a report.",
    )
    p.add_argument("results_dir", help="directory previously judged by judge.py")
    p.add_argument(
        "--report",
        default=None,
        help="markdown report destination (default: <results_dir>/report.md)",
    )
    p.add_argument(
        "--json",
        default=None,
        help="machine-readable scores destination "
        "(default: <results_dir>/scores.json)",
    )
    p.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help=f"path to config.yaml (default: {DEFAULT_CONFIG_PATH})",
    )
    p.add_argument(
        "--tasks-dir",
        default=str(REPO_ROOT / "tasks"),
        help="tasks directory (default: <repo>/tasks) — needed to read "
        "rule_check blocks at score time",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    results_dir = Path(args.results_dir).resolve()
    if not results_dir.exists():
        print(f"results dir does not exist: {results_dir}", file=sys.stderr)
        return 2

    cfg_path = Path(args.config).resolve()
    low_agreement_threshold = 0.67
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        low_agreement_threshold = float(
            cfg.get("low_agreement_threshold", low_agreement_threshold)
        )

    tasks_dir = Path(args.tasks_dir).resolve()
    if not tasks_dir.exists():
        print(f"tasks dir does not exist: {tasks_dir}", file=sys.stderr)
        return 2

    tasks_index = _load_tasks_index(tasks_dir)

    records = collect_records(results_dir, tasks_index=tasks_index)
    if not records:
        print(
            f"no transcript.json files found under {results_dir}. "
            "Run harness/run.py first.",
            file=sys.stderr,
        )
        return 2

    agg = aggregate(records, low_agreement_threshold=low_agreement_threshold)

    report_path = Path(args.report) if args.report else results_dir / "report.md"
    scores_path = Path(args.json) if args.json else results_dir / "scores.json"

    scores_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(agg, f, indent=2, default=str)

    md = render_markdown(agg)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"report  -> {report_path}")
    print(f"scores  -> {scores_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
