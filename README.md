# CLI vs CLI + Skills Benchmark

Does giving an LLM agent a Claude-style **skill library** alongside a custom CLI tool measurably improve its work? This repo runs 100 controlled tasks against three models, in two arms (CLI alone vs. CLI + skill index + `load_skill` tool), and reports the deltas.

## Hypothesis

A library of small, well-named skills — surfaced to the agent via a one-line *index* in the system prompt and loaded on demand through a `load_skill` tool — improves an agent's performance on realistic, messy work: ambiguous investigations, stateful chains, recovery from documented gotchas, and written diagnoses.

## Architecture

| Arm | What the agent gets |
|-----|---------------------|
| **A — `cli-only`** | The `ctl` CLI binary and its built-in `--help` text. One tool: `bash`. |
| **B — `cli-skills`** | Everything in A, plus a **skill index** (24 one-line `name: description` entries) injected into the system prompt, plus a second tool: `load_skill`. The agent decides which skills look relevant and loads their bodies on demand. Skill bodies are not in the system prompt. |

The architecture mirrors how Claude Code surfaces skills: `ls skills/` produces an index, and the model chooses what to read. This forces the index entries to earn their relevance — a skill that's never loaded contributes nothing.

## Results

Three OpenRouter models, single trial per task, 100 tasks per arm:

| Model | cli-only | cli-skills | Δ (skills − only) |
|-------|---------:|-----------:|------------------:|
| xiaomi/mimo-v2.5 | **0.576** [0.510, 0.642] | **0.555** [0.486, 0.624] | **−0.021** |
| qwen/qwen3.6-plus | **0.314** [0.249, 0.383] | **0.349** [0.281, 0.420] | **+0.036** |
| z-ai/glm-5.1 | **0.423** [0.351, 0.495] | **0.440** [0.367, 0.514] | **+0.018** |

Brackets are 95 % bootstrap CIs over the per-task means. Two of three deltas are positive but well within CI overlap at this trial count.

### Per-bucket signal

The headline number averages over five very different task types. The per-bucket picture is more informative:

| Bucket | xiaomi | qwen | glm |
|--------|-------:|-----:|----:|
| ambiguous (judge) | −0.112 | +0.065 | −0.069 |
| long-horizon (rules + judge) | **+0.047** | **+0.027** | **+0.094** |
| non-file (judge) | +0.002 | +0.020 | 0.000 |
| stateful (rules) | −0.053 | −0.014 | **+0.058** |
| **unplanted-failure (rules)** | **+0.070** | **+0.098** | +0.011 |

**Where skills consistently help:** `unplanted-failure` and `long-horizon`. These are the buckets where the task surfaces a documented gotcha (stale cache, partial pipeline, prerequisite chain) and the right answer is "run the documented fix." All three models gain on long-horizon; two of three gain on unplanted-failure.

**Where skills hurt or wash out:** `ambiguous` (the model's general reasoning was already strong; extra tooling adds noise) and `stateful` chains (rule-scored on tool-call patterns; the index doesn't change those patterns much for most models).

### Skill-loading behavior

The most interesting finding sits below the score line — *which* skills the agent picks, and how often it chooses to load anything at all:

| Model | Trials with zero skills loaded | Avg loads/trial | Unique skills used (of 24) |
|-------|------------------------------:|----------------:|--------------------------:|
| xiaomi/mimo-v2.5 | 51 % | 1.05 | 23 |
| z-ai/glm-5.1 | 60 % | 0.85 | 22 |
| qwen/qwen3.6-plus | 84 % | 0.26 | 17 |

Models split sharply into "engages with the index" (xiaomi, glm) and "mostly ignores it" (qwen). The latter explains why qwen's headline gain is small despite skills clearly helping when invoked — qwen rarely invokes them.

**Top-loaded skills, aggregated across all three models:**

```
18  format-output-fidelity
17  discover-runbooks
16  verify-reconcile-inventory
16  handle-suspended-account
15  paginate-list-results
14  pipeline-prerequisites
12  diagnose-refund-burst
11  resolve-triple-submit-duplicates
```

Independent convergence on the same handful of skills across three different models is meaningful: those are the ones whose descriptions actually advertise their relevance well. The bottom of the list is a mix of skills that are useful but rarely needed, and skills whose descriptions don't sell their use case crisply enough.

## Important caveat: provider non-determinism at temperature=0

OpenRouter routes requests across whatever underlying provider replica has capacity. Despite `temperature=0`, the same prompt produces different tool-call sequences and different final text on different requests. We verified this directly: across 30 sampled task pairs run twice with **bit-identical** system + user prompts, **22 produced different agent outputs**. Tool-call counts changed by up to 8 between runs.

What this means for the results above: with N=1 trials per task, sampling noise is the dominant signal at the absolute-score level. The cli-skills − cli-only **deltas** are more credible than the absolute scores, because the noise affects both arms similarly. Multi-trial averaging (`--trials 3` or higher) would tighten the CIs but at 3× the API cost. We did not run that here.

## Repository layout

```
CLI_VS_SKILLS/
├── README.md                # You are here
├── cli/                     # Custom `ctl` CLI under test
│   ├── bin/ctl
│   ├── src/                 # Subcommand implementations
│   └── README.md            # Terse `--help`-style reference (arm A sees this)
├── skills/                  # 24 individual skill files (arm B's library)
│   ├── README.md            # Skill-system documentation (humans only)
│   ├── paginate-list-results.md
│   ├── confirm-destructive-pipeline.md
│   ├── recover-pipe07-partial.md
│   └── ...                  # one .md per skill, with frontmatter
├── fixtures/                # Deterministic CLI backing data
│   ├── api/                 # JSON resource records
│   ├── pages/               # Markdown pages for `ctl fetch`
│   ├── pipelines/           # Pipeline definitions / canned results
│   └── ANOMALIES.md         # 18 documented planted gotchas (A1–A18)
├── tasks/                   # 100 benchmark tasks
│   ├── README.md            # Bucket distribution, schema, anomaly index
│   ├── 001-...yaml          # Stateful chains (001–025)
│   ├── 026-...yaml          # Ambiguous (026–050)
│   ├── 051-...yaml          # Long-horizon (051–070)
│   ├── 071-...yaml          # Unplanted failures (071–085)
│   └── 086-...yaml          # Non-file answers (086–100)
├── harness/                 # Evaluation harness
│   ├── run.py               # Run tasks across arms, record transcripts
│   ├── judge.py             # LLM-judge scoring
│   ├── score.py             # Aggregate to report
│   ├── rules.py             # Rule-based scoring evaluator
│   ├── config.yaml          # Pinned models, allowlist, paths
│   └── README.md
└── results/                 # Run artifacts (transcripts + reports)
    ├── xiaomi-mimo/
    ├── qwen-plus/
    └── zai-glm/
```

## The CLI Under Test (`ctl`)

`ctl` is a small fixture-backed CLI with a realistic surface area:

- `ctl list <resource> [--status] [--since] [--limit] [--format]`
- `ctl get <resource> <id> [--format]`
- `ctl fetch <url-or-slug>`
- `ctl search --query Q [--scope] [--i] [--reindex]`
- `ctl diff <a> <b>`
- `ctl pipeline run <name> [--confirm] [--resume] [--rollback] [--verify]`
- `ctl pipeline status <name>`
- `ctl cache status` / `ctl cache clear`

Resources: `users`, `orders`, `tickets`, `products`, `sessions`. Every command reads from `fixtures/`. No network. A pinned "now" of `2026-04-24T00:00:00Z` keeps `--since` deterministic.

`fixtures/ANOMALIES.md` documents 18 planted gotchas (A1–A18) covering pagination blindness, case-sensitive search, partial pipeline failures, prereq chains, stale caches, type-mismatched diffs, terse error messages, and so on. Tasks reference these by ID, and most skills exist to address one.

## Task Format

Tasks are YAML files with rule-based and/or judge-based scoring blocks:

```yaml
id: "027"
title: "Diagnose refund burst for user u017"
bucket: ambiguous
prompt: |
  A support escalation for u017 mentions "two orders got refunded
  really fast, something weird happened." Investigate and explain.
judge_rubric:
  - id: found_refund_pair
    criterion: "Agent identifies o088 and o091 as the refund pair."
    weight: 2
  - id: diagnosed_cause
    criterion: "Agent links the burst to the pipe-07 partial-apply incident."
    weight: 2
judge_context: |
  Ground truth: pipe-07 partial-fail on 2026-04-18 caused collateral
  refunds on o088 and o091 (owner u017). Runbook at /runbook/incident-42.
```

Stateful and unplanted-failure tasks use rule-based scoring (deterministic checks on the tool-call sequence). Ambiguous and non-file tasks use judge-based scoring. Long-horizon tasks combine both.

Distribution: 25 stateful · 25 ambiguous · 20 long-horizon · 15 unplanted-failure · 15 non-file = 100. See `tasks/README.md` for schema details.

## Skill Format

Each skill is a markdown file with YAML frontmatter:

```markdown
---
name: paginate-list-results
description: Use when running `ctl list <resource>` to retrieve more than a handful of records. The default `--limit` is 10, which silently truncates results. This skill explains how to override the limit and detect truncation.
---

# Pagination

When you run `ctl list orders`, you get up to 10 results. There are 120 orders. ...
```

The harness reads every file under `skills/` (excluding `README.md`), parses frontmatter, and renders one bullet per skill into the system prompt for arm B:

```
## Available skills

You have access to a library of skills... Call `load_skill` with `name=<n>` to read the body.

- paginate-list-results: Use when running `ctl list <resource>` to retrieve more than a handful of records...
- confirm-destructive-pipeline: Use before running pipelines like deploy-prod that refuse without `--confirm`...
- ...
```

`description` length is capped at 250 chars. `name` must equal the filename. See `skills/README.md` for authoring conventions.

## Scoring

| Bucket | Scoring | What it tests |
|--------|---------|---------------|
| Stateful chains (25) | rules | Did the agent run the discovery → handoff → action sequence on the right ID? |
| Ambiguous (25) | judge | Did the agent find the right entity and arrive at a supported conclusion? |
| Long-horizon (20) | rules + judge | Rules grade actions; judge grades any written summary or recommendation. |
| Unplanted failures (15) | rules | Did the agent detect the documented condition and run the documented fix? |
| Non-file (15) | judge | Is the written diagnosis correct, complete, and grounded in evidence? |

Judge: `claude-haiku-4.5` via OpenRouter. Three independent runs per transcript, majority vote per rubric item. Transcripts are redacted (arm-identifying strings stripped) before the judge sees them. Inter-judge agreement is recorded and low-agreement items are flagged in the report.

Task score = `(passed_weights_rules + passed_weights_judge) / (total_weights_rules + total_weights_judge)`.

## Running the benchmark

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r harness/requirements.txt
export OPENROUTER_API_KEY=sk-or-...

# Single task, smoke test
python harness/run.py --task 084 --arm cli-skills --model xiaomi/mimo-v2.5

# Full sweep, both arms
python harness/run.py --all --arm both --model xiaomi/mimo-v2.5 --out results/my-run/
python harness/judge.py results/my-run/
python harness/score.py results/my-run/
```

The harness sandboxes agent-issued shell commands behind an allowlist; `bash -c "compound ; commands"` is parsed and validated piece by piece. See `harness/README.md`.

## What this benchmark does *not* do

- **Multi-trial averaging.** Single trial per task. Provider non-determinism at temp=0 makes individual scores noisy.
- **Prompt caching.** SKILLS.md content is sent uncached on each tool-load. With caching the per-trial cost would drop substantially.
- **Cross-judge ablation.** A single judge model is used (claude-haiku-4.5). Judge variance is mitigated with N-way voting but not measured against an alternative judge.
- **Real users.** All "ambiguous" prompts are author-written; they're modeled on real support escalations but were not crowdsourced.

## License

MIT
