---
name: since-flag-formats
description: "Use when `ctl list ... --since <X>` returns `invalid date` (exit 1). The flag accepts exactly three shapes — ISO date, ISO datetime with Z, or relative (Nd/Nh). Anything else fails with no help text."
---

# `--since` accepts exactly three shapes

`ctl list ... --since <value>` validates the date strictly. On a bad
input it prints `invalid date` to stderr and exits 1, with no examples
and no hint. The accepted shapes are:

| Shape                     | Example                          |
|---------------------------|----------------------------------|
| ISO date                  | `--since 2026-04-20`             |
| ISO datetime (Z suffix)   | `--since 2026-04-18T14:30:00Z`   |
| Relative (days / hours)   | `--since 7d`, `--since 24h`      |

"Now" is pinned to `2026-04-24T00:00:00Z`, so `--since 7d` means
`2026-04-17T00:00:00Z`.

## Wrong invocations

```sh
ctl list orders --since yesterday          # invalid date
ctl list orders --since 1w                 # invalid date
ctl list orders --since 2026/04/20         # invalid date
ctl list orders --since "2026-04-18 14:30" # invalid date  (space, no Z)
ctl list orders --since 2026-04-18T14:30   # invalid date  (no Z suffix)
```

## Right invocations

```sh
ctl list orders --since 2026-04-20
ctl list orders --since 2026-04-18T14:30:00Z
ctl list orders --since 7d
ctl list orders --since 24h
```

## Common mistakes

- English words (`yesterday`, `today`, `last week`).
- Week-based relatives (`1w`). Use `7d`.
- Slashes in the date. Use ISO dashes.
- Datetime without the `Z` suffix.
