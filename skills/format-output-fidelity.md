---
name: format-output-fidelity
description: Use when piping `ctl` output to `jq`, `grep`, or any parser, or when reading any field that might exceed ~23 characters. `--format table` (the default) silently truncates long values with an ellipsis; always pass `--format json` for fidelity.
---

# `--format table` truncates silently

The default `--format table` truncates any field longer than ~23
characters with a trailing ellipsis (`…`) and no warning. That eats
ticket bodies, long product names ("Acme Earthquake Pills Mk 2"),
user-agent strings, and refund reasons.

## Wrong invocation

```sh
$ ctl get tickets t019 --format table
subject                    body                      ...
billing broken since th…   I can't check out since…  ...
```

## Right invocation

```sh
$ ctl get tickets t019 --format json
{
  "subject": "billing broken since the weekend",
  "body": "I can't check out since Saturday. Three of my recent orders..."
}
```

## When to use which

- **JSON** -- anything piped to `jq`, `grep`, a Python parser, or a
  mental diff. This is the default for any non-trivial use.
- **YAML** -- preserves fidelity but is slower to parse downstream.
  Prefer JSON.
- **Table** -- ok for human eyeballing of short fields (ids, status,
  counts). Never trust it for free-text.

## Standard idiom

```sh
ctl list orders --limit 1000 --format json \
  | jq '.[] | select(.status=="refunded")'
```

Combine with `--limit 1000` (see `paginate-list-results`); both flags
matter independently.

## Common mistakes

- Reading a truncated subject line and concluding it's the full
  subject.
- Greppting table output for a substring that lives past character 23.
- Using `--format table` and then `wc -l` to count rows -- the header
  and separator add two lines, and 10 rows is the page default anyway.
