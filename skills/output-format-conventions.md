---
name: output-format-conventions
description: Idiom -- when to choose `--format json` (machine processing, long fields, jq), `--format yaml` (rare; slow to parse), or `--format table` (default; only for short fixed fields, never free text). Prefer JSON for everything non-trivial.
---

# Output format conventions

`ctl` supports three output formats. The default is `table`, which is
the worst choice for almost any task that involves reading values
back. Pick deliberately.

## The three formats

### `--format json` -- the default you should use

A single JSON array (for `list`/`search`) or JSON object (for
`get`/`diff`/`pipeline status`). Never a stream. Full fidelity --
every character of every field is preserved.

```sh
ctl list orders --limit 1000 --format json \
  | jq '.[] | select(.status=="refunded") | .id'
```

Use for:

- Anything piped to `jq`, `grep`, a Python parser.
- Any field that might exceed ~23 characters: ticket bodies,
  user-agent strings, refund reasons, long product names.
- Any cross-tool comparison (e.g. `diff <(...) <(...)`).

### `--format yaml` -- rarely the right choice

Preserves fidelity like JSON, but is slower to parse downstream and
harder to pipe into `jq`. Prefer JSON unless a downstream consumer
specifically wants YAML.

### `--format table` -- the default; eyeball-only

Truncates any field longer than ~23 characters with a `…` ellipsis
and no warning. See `format-output-fidelity` for the gory details.

OK for: ids, statuses, counts, short enums. Never for free text.

## Standard idiom block

Put these two flags on every `list` and `search` you actually intend
to use:

```sh
--limit 1000 --format json
```

`--limit 1000` because of `paginate-list-results`. `--format json`
because of `format-output-fidelity`. They're independent traps.

## Common mistakes

- Defaulting to `table` because it "looks nicer." It silently drops
  data.
- Using YAML by habit; you'll spend extra time parsing.
- Forgetting that a single record (`ctl get`) is a JSON object, not
  an array -- `jq '.[] ...'` will not work; use `jq '.field'`.
