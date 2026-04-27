---
name: lookup-resource-by-id
description: Use when `ctl get <resource> <id>` returns `not found` (exit 1) and you don't have the exact id. There is no fuzzy match or "did you mean" hint; search by name first, then `get` the canonical id.
---

# `ctl get` is exact-match only

`ctl get <resource> <id>` either finds the record by exact id or exits
1 with stderr of exactly `not found`. There is no fuzzy match, no
"nearby ids" list, no suggestion.

## Wrong invocation

```sh
$ ctl get users u999
not found
$ echo $?
1
```

## Right pattern: search, then get

```sh
$ ctl search --query "sarah.chen" --scope users --i --format json
[{"id": "u042", "name": "Sarah Chen", ...}]
$ ctl get users u042 --format json
```

Notes:

- `--i` is required if your query is lowercase but the field value is
  capitalised (see `case-insensitive-search`).
- `--format json` keeps long fields intact (see
  `format-output-fidelity`).
- Email and name searches both work; either tends to be enough to
  recover an id.

## Resource id prefixes

| prefix | resource |
|--------|----------|
| `u`    | users    |
| `o`    | orders   |
| `t`    | tickets  |
| `p`    | products |
| `s`    | sessions |

Three-digit suffix, zero-padded.

## Common mistakes

- Guessing nearby ids (`u042` -> `u041`, `u043`). The CLI gives no
  signal whether you're close.
- Running `ctl list users` and grepping by name -- works, but only if
  you remembered to pass `--limit 1000` (see `paginate-list-results`).
