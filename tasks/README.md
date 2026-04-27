# `tasks/` — Benchmark Task Library

This directory holds the 100 benchmark tasks (plus `000-stub.yaml`, a smoke-test
task written by the harness agent) that the CLI vs CLI + Skills experiment runs
against. Each task is a self-contained YAML file scored by deterministic
`rule_check` assertions, an LLM judge's `judge_rubric`, or both (hybrid).

## Bucket distribution

| Bucket | Count | Id range |
|---|---:|---|
| `stateful` | 25 | 001–025 |
| `ambiguous` | 25 | 026–050 |
| `long-horizon` | 20 | 051–070 |
| `unplanted-failure` | 15 | 071–085 |
| `non-file` | 15 | 086–100 |

## Scoring mode per bucket

The root `README.md` (see "Task Format" and "Scoring") defines the authoritative
`rule_check` schema. Per-bucket conventions in this library:

| Bucket | Scoring mode | Blocks present |
|---|---|---|
| `stateful` (001–025) | pure rule_check | `rule_check` only |
| `ambiguous` (026–050) | pure judge | `judge_rubric` + `judge_context` only |
| `long-horizon` (051–070) | hybrid | `rule_check` + `judge_rubric` (+ `judge_context`) |
| `unplanted-failure` (071–085) | pure rule_check | `rule_check` only |
| `non-file` (086–100) | pure judge | `judge_rubric` + `judge_context` only |

Rule-checked tasks assert tool-call patterns (argv regex, sequence, negative
guards, exit codes) and optional final-text matches. Judge-scored tasks delegate
to the LLM judge for criteria that depend on *what the agent wrote*, not just
*what they ran*. Hybrid long-horizon tasks put action-verifiable criteria in
`rule_check` and written-deliverable criteria (e.g. "Final report compares
before/after counts") in `judge_rubric`.

Validate bucket/block conformance with:

```bash
python harness/_test_task_rules.py
```

The buckets are defined in the root `README.md` (see "Task Taxonomy"). Briefly:

- **stateful** — list → pick an id from output → act on that id.
- **ambiguous** — fuzzy under-specified prompts; judge grades entity
  identification + line of inquiry + supported conclusion.
- **long-horizon** — multi-step migrations/reconciliations with checkpoints;
  judge grades intermediate states, not just endpoint.
- **unplanted-failure** — the task is normal, the environment bites; judge
  grades detection and recovery.
- **non-file** — the output is an explanation; judge grades correctness and
  completeness of the written answer.

## Tag vocabulary

Tags are used by `harness/score.py` for cross-task breakdowns. Vocabulary:

- Resource: `users`, `orders`, `tickets`, `products`, `sessions`
- Surface area: `search`, `fetch`, `diff`, `pipelines`, `cache`, `format`,
  `ids`, `time-window`
- Anomaly ids: `A1` … `A18` (see `fixtures/ANOMALIES.md`)
- Pipeline ids: `pipe-01` … `pipe-09`
- Key entities: `u017`, `u042`, `pipe-07`, etc.
- Classes of skill: `pagination`, `aggregation`, `investigation`,
  `reasoning`, `triage`, `breadth`, `duplicates`, `migration`, `writing`,
  `documentation`, `executive`, `post-mortem`, `stateful`, `basic-chain`,
  `clarification`, `meta`, `nulls`, `priority`, `ordering`

When adding a task, prefer an existing tag over inventing a new one.

## Schema

See the root `README.md` "Task Format" and "Scoring" sections for the
authoritative YAML schema (including the `rule_check` grammar). Minimal
requirements enforced by convention:

- `id`: 3-digit zero-padded string matching the filename prefix.
- `title`: one-line human-readable title.
- `bucket`: exactly one of `stateful` | `ambiguous` | `long-horizon` |
  `unplanted-failure` | `non-file`.
- `prompt`: multi-line prompt shown to the agent (natural language).
- `setup` (optional): shell commands run before the agent starts.
- `rule_check` (present for `stateful`, `long-horizon`, `unplanted-failure`):
  2–8 assertions with small positive integer `weight`s; total weight per task
  in the 3–9 range.
- `judge_rubric` (present for `ambiguous`, `long-horizon`, `non-file`): 1–6
  binary criteria with small positive integer `weight`s; total weight per task
  in the 1–8 range.
- `judge_context` (required when `judge_rubric` is present): ground truth for
  the judge — factual, precise, enough that a blind judge can grade without
  prior knowledge of the fixture.
- `tags`: free-form from the vocabulary above.

## Authoring conventions

1. **Prefer `rule_check` when the correctness signal is an action pattern.**
   Stateful chains, unplanted-failure recovery, and long-horizon action
   checkpoints are all verifiable by argv regex + sequence order.
2. **Pair positive rules with negative guards.** e.g. positive = "called with
   `--limit >= 200`"; negative = "did NOT stop after a bare `ctl list orders`".
3. **Keep judge criteria to written deliverables.** For hybrid tasks, move
   "ran the right command" into `rule_check` and leave "explained why"
   criteria in `judge_rubric`.
4. **Make every rubric item judgeable from the transcript alone.** No "agent
   was confident" or "response felt correct" criteria. Grade commands run,
   ids referenced, or explicit claims in the final answer.
5. **Vary resources across a bucket.** Don't let all 25 stateful tasks be
   about users.
6. **Make `judge_context` self-contained.** The judge has no prior knowledge
   of fixtures or anomalies; the ground truth section must be enough.
7. **For open-ended tasks, grade reasoning not a specific id.** If multiple
   answers are defensible, say so in `judge_context` and grade internal
   consistency between transcript evidence and the agent's claim.
8. **Reference anomalies by id.** Tag with `A1`…`A18` so score aggregation
   can surface which anomalies agents trip on.

## How to add a new task

1. Pick the next unused 3-digit id (note: `000` is the harness smoke-test
   stub; the production library is 001–100).
2. Create `tasks/<id>-<slug>.yaml`, where `<slug>` is a short kebab-case
   description of the task (e.g. `042-refund-burst-u017.yaml`).
3. Fill in the schema. Start with an exemplar task from the same bucket:
   - stateful: `tasks/004-escalated-ticket-thread.yaml`
   - ambiguous: `tasks/027-refund-burst-u017.yaml`
   - long-horizon: `tasks/051-pipe07-full-recovery.yaml`
   - unplanted-failure: `tasks/073-unplanted-pipe07-partial.yaml`
   - non-file: `tasks/086-non-file-explain-pipe07.yaml`
4. Keep total rubric weight in 3–8. Use weight 1 for routine checks and
   weight 2–3 for the item that most discriminates correct from incorrect.
5. Run `python harness/run.py --task <id> --arm cli-only` once on a cheap
   agent to sanity-check the task is solvable at all.

## How to validate YAML

The harness expects a superset of the schema above. Minimal lint:

```bash
python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" tasks/*.yaml
```

Recommended richer check (enforces per-bucket scoring blocks and rule_check
schema):

```bash
python harness/_test_task_rules.py
```

## Anomaly coverage (reverse index)

Every planted anomaly A1–A18 from `fixtures/ANOMALIES.md` is exercised by at
least one task. Mapping:

- **A1** (pagination / default limit 10): 003, 005, 006, 009, 015, 017, 018,
  021, 027, 031, 033, 034, 040, 052, 060, 064, 071, 083, 089
- **A2** (pipe-01 `--confirm`): 044, 063, 084
- **A3** (pipe-05 requires pipe-03): 019, 047, 054, 062, 074, 095
- **A4** (pipe-03 invalidates fetch cache): 025, 062, 085
- **A5** (search case-sensitivity): 010, 020, 026, 029, 038, 049, 076
- **A6** (search index stale post-pipe-07): 029, 059, 062, 065, 077, 097
- **A7** (`/docs/auth` canned 404): 020, 030, 059, 070, 072
- **A8** (diff silent on type mismatch): 008, 021, 043, 078
- **A9** (`--since` terse error): 039, 045, 067, 082
- **A10** (pipe-07 partial 147/200 + o088/o091 collateral): 014, 027, 032,
  046, 051, 055, 061, 064, 068, 069, 070, 073, 080, 086, 091, 093, 100
- **A11** (pipe-09 false-OK without `--verify`): 023, 028, 048, 057, 061,
  070, 075, 088, 094, 100
- **A12** (`ctl get` terse not-found): 042, 080, 099
- **A13** (`--format table` truncation): 041, 081
- **A14** (triple-submit o067/o068/o069 + keep-lowest convention): 024, 031,
  058, 096
- **A15** (u042 Sarah Chen suspended + t019 + flagged o102/o107/o115): 004,
  009, 010, 012, 016, 026, 036, 038, 050, 056, 061, 066, 070, 076, 087, 090,
  100
- **A16** (runbook at /runbook/incident-42 reachable via /docs/troubleshooting):
  011, 027, 085, 086, 091
- **A17** (pipe-04 exit 0 + stderr + /tmp/pipe-04.skipped): 013, 053, 062,
  068, 079, 098
- **A18** (u023/u031/u049 null-emails): 033, 060, 083
