# Harness

Three scripts drive the CLI_VS_SKILLS benchmark end-to-end.

| Script | Purpose |
|---|---|
| `run.py` | Executes tasks against one or both arms, records transcripts. |
| `judge.py` | Grades transcripts with an LLM judge (blinded, redacted). |
| `score.py` | Aggregates judgements into `scores.json` and `report.md`. |

All three read `harness/config.yaml` for pinned models, limits, and paths.

The harness talks to model providers through **OpenRouter** using the
OpenAI-compatible SDK. OpenRouter proxies Anthropic, OpenAI, Google,
Meta, Mistral, and more behind one API — which means you can swap the
agent / judge models with a one-line config change and no code edits.

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r harness/requirements.txt
```

## Auth

Set `OPENROUTER_API_KEY` in the environment. `run.py` and `judge.py` refuse
to start without it; `--dry-run` on `run.py` is the only network-free entry
point. Grab a key at https://openrouter.ai/keys.

```bash
export OPENROUTER_API_KEY=sk-or-...
```

If you want to target a different OpenAI-compatible gateway (LiteLLM,
self-hosted vLLM, Ollama's OpenAI shim, an internal proxy, etc.), set
`api_base_url` in `harness/config.yaml`. The same `OPENROUTER_API_KEY` env
var will be sent as the bearer token — rename it in code if you need a
different variable.

## Model slugs

OpenRouter uses `<provider>/<model-name>` slugs (e.g.
`anthropic/claude-opus-4.7`, `openai/gpt-4o`, `google/gemini-2.5-pro`).
Browse available models at https://openrouter.ai/models and update
`agent_model` / `judge_model` in `harness/config.yaml` to match.

Keep the agent and judge in **different families** so the judge isn't
rewarding its own style.

## Run one task

```bash
# Dry-run: assemble the system + user prompts and print them. No API calls.
python harness/run.py --task 000 --arm cli-only --dry-run

# Live run, single arm.
python harness/run.py --task 000 --arm cli-only

# Both arms, three trials each.
python harness/run.py --task 000 --arm both --trials 3
```

Results land under `results/<UTC-timestamp>/<task>/<arm>/trial_<n>/` and
contain:

- `transcript.json` — full message history, tool calls, usage, timings.
- `ctl-state/` — per-trial `CTL_STATE_DIR` (created fresh, never reused).
- `artifact.<ext>` — any `/tmp/task-*.*` path mentioned in the prompt that
  existed on disk after the run.

## Run the whole suite

```bash
python harness/run.py --all --arm both --trials 1 \
  --out results/full-$(date -u +%Y%m%dT%H%M%SZ)/
```

Filter by bucket if you just want the hard stuff:

```bash
python harness/run.py --all --only-bucket ambiguous
```

## Scoring modes

Every task must declare at least one of two grading blocks. Tasks that declare
neither are malformed and `run.py` rejects them at load time.

| Block | What it is | API calls |
|---|---|---|
| `rule_check` | Deterministic assertions run against the transcript. | **None.** |
| `judge_rubric` | Binary criteria graded by the LLM judge. | N per transcript (see `--judges`). |
| both | Weighted union of the two. | Same as `judge_rubric`. |

A task may declare only `rule_check` (pure rule-scored — the judge is never
called, and `judge.py` emits a placeholder `judgement.json` marked
`judge_skipped: true`), only `judge_rubric` (existing behavior, unchanged), or
both.

### How scores combine

```
combined = (sum_passed_rule_weights + sum_passed_judge_weights)
         / (sum_rule_weights       + sum_judge_weights)
```

If only one block is present, the combined score is just that block's
pass-fraction. Per-bucket means and the headline delta use the `combined`
score — they don't care which source produced it.

`score.py` records both sub-scores on every record so the report can show a
`rule_score | judge_score | combined` breakdown per task. It also prints a
summary counting rule-only, judge-only, and hybrid tasks.

### Rule assertions reference

`rule_check` is a list of items; each has an `id`, an `assert`, a `weight`,
and assert-specific fields. Supported assertions:

| `assert` | Checks |
|---|---|
| `tool_called` | At least one transcript tool call matches `match`. |
| `no_tool_called` | Zero transcript tool calls match `match`. |
| `tool_sequence` | Every predicate in `sequence` matches a tool call, in order (non-contiguous). |
| `final_text_regex` | The agent's `final_text` matches `pattern` (regex). |
| `final_text_contains` | The agent's `final_text` contains `text` (substring). |
| `exit_code_seen` | At least one tool call matches `match` AND returned `match.exit_code`. |

Predicate fields (inside `match` for most assertions, inside each `sequence`
entry for `tool_sequence` — all optional, AND semantics):

- `argv_prefix: [str, ...]` — argv tokens start with this prefix (after shell-style tokenisation).
- `argv_regex: "..."` — regex on the joined argv string (after `bash -c` unwrapping; see below).
- `stdout_regex: "..."` — regex on tool call stdout.
- `stderr_regex: "..."` — regex on tool call stderr.
- `exit_code: <int>` — tool call exit code equals this value.

Text-assertion fields:

- `pattern` (final_text_regex) / `text` (final_text_contains) — required.
- `case_sensitive: bool` — defaults to `false` (configurable via
  `scoring.default_case_sensitive_text_match`).

#### `bash -c` unwrapping

Agents regularly run compound commands via
`bash -c "ctl list orders | grep foo"`. For rule matching, the harness
unwraps these: the effective argv list becomes the tokenised inner command,
and the inner command is split on `;`, `&&`, `||`, `|` (the same operators
`run.py`'s allowlist splits on). **A rule against one tool call passes if any
sub-command of the compound matches.**

So `argv_regex: "^ctl list users"` matches all of:

- `ctl list users`
- `bash -c "ctl list users"`
- `bash -c "ctl list users | grep foo"`
- `bash -c "cat /tmp/xx && ctl list users"`

Regex compile errors fail the individual rule item with a `regex compile
error: ...` note — the rest of the evaluation continues.

### Example hybrid task

```yaml
rule_check:
  - id: listed_tickets
    assert: tool_called
    match:
      argv_regex: "^ctl (list|search) .*tickets"
    weight: 1
  - id: no_wrong_user
    assert: no_tool_called
    match:
      argv_regex: "^ctl get users u(?!042)\\d{3}"
    weight: 1
  - id: ran_recovery_after_status
    assert: tool_sequence
    sequence:
      - argv_regex: "^ctl pipeline status pipe-07"
      - argv_regex: "^ctl pipeline run pipe-07 --(resume|rollback)"
    weight: 2
  - id: final_mentions_runbook
    assert: final_text_regex
    pattern: "incident-?42|runbook"
    weight: 1
  - id: pipe01_refused
    assert: exit_code_seen
    match:
      argv_regex: "^ctl pipeline run pipe-01"
      exit_code: 2
    weight: 1

judge_rubric:
  - id: diagnosed_cause
    criterion: "Final explanation correctly links the refund to pipe-07 partial-write."
    weight: 2
```

## Judge the transcripts

```bash
python harness/judge.py results/<ts>/
```

Flags:

- `--judges N` — number of independent judge runs per transcript (default 3).
  Must be odd so majority vote has a clear winner; evens are allowed but ties
  resolve to fail (the warning is printed).
- `--judge-model MODEL` — override `judge_model` from config. Keep it in a
  different family from `agent_model`. Use an OpenRouter slug, e.g.
  `openai/gpt-4o-mini` or `google/gemini-2.5-flash`.
- `--redact` / `--no-redact` — on by default. Redaction replaces arm labels
  (`cli-only`, `cli-skills`, `SKILLS.md`, section headers) with the token
  `[REDACTED-REFERENCE]` before the judge sees the transcript.
- `--force` — re-judge transcripts that already have `judgement.json`.

Output: `judgement.json` beside each `transcript.json`. It records every
judge run's raw output, the parsed scores, the majority vote per rubric item,
the per-item inter-judge agreement, and the final `task_score`.

## Score and report

```bash
python harness/score.py results/<ts>/
```

Writes:

- `results/<ts>/report.md` — headline, per-bucket, per-task deltas, low-
  agreement callouts, efficiency, diagnostics.
- `results/<ts>/scores.json` — same data, machine-readable.

Override destinations with `--report` and `--json`.

## Re-judging

```bash
# Everything.
python harness/judge.py results/<ts>/ --force

# One specific trial — just point judge.py at that subdir; it still walks
# recursively and only cares about transcript.json / judgement.json.
python harness/judge.py results/<ts>/042/cli-skills/trial_0/ --force
```

## Skill loading

The `cli-skills` arm uses a Claude-style skill library: every skill is its
own `.md` file under `skills/` (`skills_dir` in `config.yaml`) with a YAML
frontmatter block:

```markdown
---
name: paginate-list-results
description: Use when running `ctl list <resource>` to count records or filter to "all" of something...
---

# Pagination
...body...
```

`name` MUST equal the filename stem; `description` is one sentence ≤ 250
chars. `skills/README.md` is documentation for humans, not a skill — the
harness skips it (and any other file without a parseable frontmatter
block).

### Index → tool flow

The system prompt for `cli-skills` only carries an *index* of every skill
(name + description), not the bodies. The agent sees a second tool
alongside `bash`:

```
load_skill(name: string)
```

When the agent decides a skill looks relevant, it calls `load_skill` and
the harness returns the body as the tool result. Loading a missing name
returns a structured `{"error": "skill not found", ...}` JSON payload so
the agent can recover. Every load is logged in the transcript:

```json
{
  "skills_loaded": ["paginate-list-results", "confirm-destructive-pipeline"],
  "skill_load_calls": [
    {"turn": 0, "tool_use_id": "...", "name": "paginate-list-results", "found": true, "duplicate": false},
    {"turn": 2, "tool_use_id": "...", "name": "paginate-list-results", "found": true, "duplicate": true}
  ]
}
```

The `cli-only` arm is unchanged — it still gets only `cli/README.md` in
the system prompt and only the `bash` tool.

### Token cost shape

The per-task system prompt for `cli-skills` is now substantially
cheaper: only the index (~one short bullet per skill) ships on every
turn, instead of the entire skill library. The tradeoff is that each
skill the agent loads sends its body once as a `tool_result` message.
For tasks where the agent only needs one or two skills this is a clear
win; for tasks that need every skill (rare) it costs a few extra tokens
relative to the old monolithic prompt.

If `skills/SKILLS.md` (the legacy monolithic file) is still present,
`run.py` ignores it and prints a deprecation warning at startup.

## The allowlist

`run.py` exposes exactly one tool to the agent: `bash`. Every command is
validated before execution:

1. **argv[0] must match `allowed_argv0`** in `config.yaml`. As shipped:
   `./cli/bin/ctl`, `ctl`, `cat`, `ls`, `mkdir`, `head`, `tail`, `wc`, `grep`,
   `jq`, `python3`, `echo`, `bash`.
2. **`bash` is only accepted as `bash -c "<inner>"`**. The inner string is
   recursively re-validated — you can chain sub-commands with `;`, `&&`, `||`,
   or `|`, and each sub-command must itself pass the allowlist.
3. **Redirects (`>`, `>>`)** are only honored when the target path begins with
   one of the `writable_paths` prefixes (default `/tmp/` and `$CTL_STATE_DIR`
   / `$WORKDIR`, resolved against the trial's actual directories).
4. **Command substitution** (`` `...` ``, `$(...)`) and process substitution
   (`<(...)`, `>(...)`) are always rejected. We can't sandbox arbitrary
   expressions — agents that need that behavior must write a python3 script
   and invoke it explicitly.
5. **Per-command timeout** is 30s (configurable via
   `per_command_timeout_seconds`).
6. Rejected commands are returned to the agent as structured tool_result
   errors — the agent sees the reason and can retry. Every rejection is also
   logged under `rejected_commands` in the transcript.

## Environment per trial

- `CTL_STATE_DIR` — freshly created at `<workdir>/ctl-state` before each
  trial. Removed (if it existed) and re-created empty. Never reused across
  trials.
- `CTL_FIXTURES_DIR` — set to `<repo>/fixtures` if that directory exists.
- `WORKDIR` — set to the trial directory, used when resolving writable
  prefixes like `$WORKDIR/`.
- cwd = repo root (so `./cli/bin/ctl` resolves).
- All other env vars from the shell that launched `run.py` are inherited.

## Config reference (`harness/config.yaml`)

| Key | Purpose |
|---|---|
| `agent_model` | Model under evaluation. OpenRouter slug (`provider/model`). |
| `judge_model` | Judge model. Must be a different family. OpenRouter slug. |
| `api_base_url` | OpenAI-compatible endpoint. Defaults to OpenRouter. |
| `max_turns` | Max agent loop iterations per trial. |
| `per_command_timeout_seconds` | Timeout for each bash tool call. |
| `judges_per_transcript` | Default `--judges` for `judge.py`. |
| `low_agreement_threshold` | Score below this = flagged in report. |
| `allowed_argv0` | argv[0] allowlist. |
| `writable_paths` | Prefixes redirects may target. |
| `skills_dir` | Directory of one-skill-per-file `.md` files for the cli-skills arm. |
| `results_root` | Default root for `--out`. |
| `stdout_cap_bytes` / `stderr_cap_bytes` | Per-tool-call output truncation cap. |
| `agent_max_tokens` / `judge_max_tokens` | Per-call max_tokens. |
| `pinned_now` | Recorded in manifest; CLI should honor for `--since`. |

## TODO: prompt caching

The skill-index block in the cli-skills system prompt is identical
across all tasks, and the cli/README.md block is identical across both
arms. Caching either block would save input tokens on a full sweep —
proportionally less than the old monolithic SKILLS.md prompt (since the
index is much smaller), but still real.

OpenRouter supports Anthropic-style `cache_control` breakpoints on
content-block messages when the upstream provider is Anthropic, but
plumbing that through the OpenAI SDK's `chat.completions.create` cleanly
requires passing content-block dicts (not strings) as the `system`
message and using `extra_body` to forward provider-specific flags.
That path is under-documented for this SDK version, so we skipped it in
v1 to keep the request shape boring and portable across providers.

If you want to add it: switch to a list of text blocks for the system
message with `cache_control: {type: "ephemeral"}` on the cli/README.md
and skill-index blocks, verify
`usage.prompt_tokens_details.cached_tokens` comes back non-zero on the
second request, and record it under
`transcript["usage"]["cache_read_input_tokens"]` (which is already a
first-class field).
