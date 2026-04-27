---
name: resource-id-conventions
description: Idiom -- ctl ids follow a one-letter-prefix + three-digit-suffix convention (`u`/`o`/`t`/`p`/`s`). Use to validate ids before `ctl get`/`diff` and to recognise canonical "key identities" (u017, u042, t019, p014, etc).
---

# Resource id conventions

Every record in `ctl` has an id of the form `<prefix><NNN>` where
`<prefix>` is a single letter naming the resource and `<NNN>` is a
zero-padded three-digit number.

| prefix | resource | example | row count |
|--------|----------|---------|----------:|
| `u`    | users    | `u042`  | 50        |
| `o`    | orders   | `o088`  | 120       |
| `t`    | tickets  | `t019`  | 30        |
| `p`    | products | `p014`  | 80        |
| `s`    | sessions | `s003`  | 15        |

## Why this matters

### Validate before `diff`

`ctl diff` does not check that two ids share a resource. `ctl diff
u001 o001` returns `{}` and exits 0 -- which looks identical to "no
differences." Always check the prefix first. See
`diff-resource-type-validation`.

### Validate before `get`

`ctl get` takes the resource AS THE FIRST ARG. The id prefix is
informational, not authoritative -- `ctl get orders u042` will exit
1 with `not found`. Make sure the resource arg matches the id
prefix.

```sh
ctl get users u042       # right
ctl get orders u042      # wrong; not found
```

## Key identities to remember

These ids show up across many tasks:

| id    | meaning                                                          |
|-------|------------------------------------------------------------------|
| u017  | owns 14 orders; pipe-07 collateral refunds o088 and o091         |
| u042  | Sarah Chen; suspended 2026-04-22; flagged orders o102/o107/o115  |
| u008  | owns triple-submit o067/o068/o069                                |
| u023, u031, u049 | users with `email: null`                              |
| o088, o091 | pipe-07 collateral refunds                                  |
| o067, o068, o069 | triple-submit set                                     |
| o102, o107, o115 | Sarah Chen's flagged orders                           |
| t019  | Sarah Chen's escalated billing ticket                            |
| p014, p037, p061 | pipe-09 inventory discrepancies                       |
| p044, p077 | skipped by pipe-04                                          |

When a task names any of these ids, the relevant skill should be
obvious. Cross-reference the ids before drawing conclusions.

## Common mistakes

- Treating ids from different resources as comparable.
- Mixing up resource arg and id prefix in `ctl get`.
- Forgetting that the three-digit suffix is zero-padded -- `u42` is
  not `u042`.
