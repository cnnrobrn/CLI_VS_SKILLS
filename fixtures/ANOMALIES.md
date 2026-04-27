# Planted Anomalies

This file documents every deliberately planted anomaly in the `ctl` fixture
set. Each one is reproducibly triggerable from a `ctl` invocation. Benchmark
tasks reference these by ID (A1 ... A18). Pinned "now" is
`2026-04-24T00:00:00Z`.

The **task-authoring agent** and the **judge** read this file. The agent
under test does NOT. The `SKILLS.md` file teaches recovery / idioms based on
these anomalies, but without referring to the A-codes.

---

## A1 -- pagination blindness

`ctl list` defaults to `--limit 10`. The underlying datasets are:

| resource | rows |
|----------|----:|
| users    |  50 |
| orders   | 120 |
| tickets  |  30 |
| products |  80 |
| sessions |  15 |

All but `sessions` exceed the default. There is no `--count` flag, no
"truncated" banner, and no warning on stderr. To see all rows pass
`--limit 1000` (or any number >= the table size).

If `--limit` receives a non-integer, stderr says only `--limit must be an
integer` -- no examples.

**Trigger:**
```
ctl list orders            # first 10 only
ctl list orders --limit 1000
```

---

## A2 -- `deploy-prod` refusal

`ctl pipeline run pipe-01` (name: `deploy-prod`) exits `2` with a bare
`refused` on stderr. Succeeds with `--confirm`. The CLI gives no hint that
`--confirm` exists.

**Trigger:**
```
ctl pipeline run pipe-01              # -> stderr: refused, exit 2
ctl pipeline run pipe-01 --confirm    # -> ok, exit 0
```

Also refused without `--confirm`: `pipe-06 purge-audit-logs`.

---

## A3 -- `pipe-05` prerequisite

`ctl pipeline run pipe-05` (name: `reindex-search`) requires `pipe-03`
(name: `rotate-keys`) to have run in the current state dir. If it has not,
pipe-05 exits `2` with stderr `prerequisite not met`. The CLI does NOT
disclose which pipeline is the prereq.

Prereq tracking lives at `$CTL_STATE_DIR/pipe-03_ran.json`. Wiping the state
dir resets the requirement.

**Trigger:**
```
rm -rf ~/.ctl-state
ctl pipeline run pipe-05              # -> stderr: prerequisite not met, exit 2
ctl pipeline run pipe-03              # -> ok
ctl pipeline run pipe-05              # -> ok
```

---

## A4 -- pages cache stale after `pipe-03`

Running `pipe-03` marks the page cache stale. Every subsequent
`ctl fetch /docs/*` returns a canned 404 body (see
`fixtures/pages/_stale_404.md`) until `ctl cache clear` (or
`ctl cache clear pages`) is run. Non-`/docs/` slugs (e.g. `/runbook/*`,
`/help/*`) are unaffected.

**Trigger:**
```
ctl fetch /docs/pagination            # -> real page
ctl pipeline run pipe-03              # -> ok, marks cache stale
ctl fetch /docs/pagination            # -> 404 body (exit 0)
ctl cache clear                       # -> cleared
ctl fetch /docs/pagination            # -> real page again
```

---

## A5 -- search case sensitivity

`ctl search --query Q` is case-sensitive. Useful specifically:

| query         | scope=products | result            |
|---------------|---------------:|-------------------|
| `acme`        | products       | 0 rows            |
| `Acme`        | products       | 12 rows           |
| `acme --i`    | products       | 12 rows           |

The `acme` variants live in product names as "Acme Foghorn", "Acme Anvil",
"Acme Rocket Skates", "Acme Earthquake Pills" (and three more at `Mk 1`,
`Mk 2`).

---

## A6 -- stale search index disagrees with `list`

After running `pipe-07` (`--resume` or `--rollback`), the search index is
marked stale. `ctl list orders --status paid` and
`ctl search --query "status:paid" --scope orders` then disagree on two
specific orders: `o088` and `o091`.

- `ctl list` reflects the underlying fixture state: both are `refunded`.
- `ctl search` with the stale index still reports them as `paid`.

`ctl search --reindex` fixes it.

**Trigger:**
```
ctl pipeline run pipe-07 --resume
ctl list orders --status paid --limit 200 --format json | jq 'length'
# -> 36, without o088/o091
ctl search --query "status:paid" --scope orders | jq 'length'
# -> 38, with o088/o091
ctl search --reindex
ctl search --query "status:paid" --scope orders | jq 'length'
# -> 36
```

---

## A7 -- `/docs/auth` stale cache 404

`ctl fetch /docs/auth` returns the canned 404 body by default, simulating
a stale cache entry. `ctl cache clear` (or
`ctl cache clear pages`) repairs it: subsequent fetches serve the real
page. A freshly-wiped `$CTL_STATE_DIR` puts the anomaly back.

Unlike A4 (which only affects `/docs/*` AFTER pipe-03 runs), A7 affects
`/docs/auth` from the start -- the agent sees a 404 immediately without
doing anything.

**Trigger:**
```
rm -rf ~/.ctl-state
ctl fetch /docs/auth                  # -> 404 body (exit 0)
ctl cache clear                       # writes the auth_cache_ok sentinel
ctl fetch /docs/auth                  # -> real docs page
rm -rf ~/.ctl-state
ctl fetch /docs/auth                  # -> 404 body again (default)
```

---

## A8 -- `diff` across resource types silently returns `{}`

`ctl diff u001 o001` exits `0` and prints `{}`. No error, no warning. Only
diffs of ids from the same resource produce a real diff.

**Trigger:**
```
ctl diff u001 o001                    # -> {}    (exit 0)
ctl diff u001 u002                    # -> structured diff
```

---

## A9 -- `--since garbage` is terse

`ctl list orders --since garbage` fails with stderr of exactly
`invalid date` and exit 1. No format hint.

Accepted forms:
- `2026-04-20` (ISO date)
- `2026-04-20T12:00:00Z` (ISO datetime)
- `7d` / `24h` (relative)

---

## A10 -- `pipe-07` partial-apply collateral damage (pre-baked)

`ctl pipeline run pipe-07` (name: `backfill-orders`) is documented with
this permanent lore:

- **The fixtures reflect the post-partial-failure state.** Running
  `pipe-07` with no flag prints `already partially applied` to stderr and
  exits `1`.
- `ctl pipeline status pipe-07` shows `completed: 147/200, remaining: 53,
  state: partial`, plus `failed_at: 2026-04-18T14:42:09Z` and the
  collateral-refund list: `o088, o091`.
- Orders `o088` and `o091` (both belonging to user `u017`) are pre-set to
  `status=refunded`, `refund_source=pipe-07`, with `refunded_at`
  timestamps on 2026-04-18 within an hour of each other (14:48 and 15:21).
- Recovery: `ctl pipeline run pipe-07 --resume` finishes the remaining 53;
  `ctl pipeline run pipe-07 --rollback` reverts the 147. Both actions also
  mark the search index stale (A6).
- User `u017` has 14 orders in total, which forces any "look at all of
  u017's orders" task to page past the `--limit 10` default.

---

## A11 -- `pipe-09` false OK unless `--verify`

`ctl pipeline run pipe-09` (name: `reconcile-inventory`) exits `0` with
`pipeline reconcile-inventory: ok` -- but does not actually reconcile
anything. Only `--verify` runs the comparison pass, prints

    pipeline reconcile-inventory: ok, verified: true, discrepancies: 3

and emits the list of three discrepant product ids: `p014`, `p037`,
`p061`. Each of those product records carries an `inventory_discrepancy`
block documenting the delta and a note.

| product | recorded | warehouse | delta | note                                             |
|---------|--------:|---------:|-----:|--------------------------------------------------|
| p014    |     120 |      117 |   -3 | recorded 120, warehouse reports 117              |
| p037    |      42 |       50 |   +8 | recorded 42, warehouse reports 50                |
| p061    |       0 |        5 |   +5 | recorded 0, warehouse reports 5 (phantom oos)    |

---

## A12 -- unknown id: terse `not found`, no suggestion

`ctl get users u999` exits `1`, stderr is exactly `not found`. No fuzzy
matching, no "did you mean u042?" suggestion, no list of nearby ids.

---

## A13 -- `--format table` silently truncates long fields

Any field longer than 23 characters is rendered with a trailing ellipsis
`…` and no indication that truncation happened. `--format json` is full
fidelity. Easy to miss on ticket bodies, user_agent strings, and product
names with `Mk N` suffixes.

---

## A14 -- triple-submit duplicate orders (`o067`, `o068`, `o069`)

All three orders have `user_id = u008`, `total_cents = 4999`, and
`created_at` timestamps on `2026-04-10T08:12:15Z`, `...16Z`, `...17Z`
respectively (3 seconds apart). Two are refunded
(`refund_reason = "duplicate submission (triple-submit)"`) and one
remains `paid`.

Convention (from `/help/duplicates`): keep the lowest id as `paid` and
refund the others. That means `o067` paid, `o068` + `o069` refunded --
which is exactly how the fixtures are seeded.

---

## A15 -- Sarah Chen (`u042`)

| field              | value                                                    |
|--------------------|----------------------------------------------------------|
| id                 | u042                                                     |
| email              | sarah.chen@acme.io                                       |
| name               | Sarah Chen                                               |
| status             | suspended                                                |
| status_changed_at  | 2026-04-22T11:47:00Z                                     |
| org_id             | org-2                                                    |
| notes              | billing dispute; account flipped to suspended pending review |

Sarah has 3 flagged orders: `o102`, `o107`, `o115` (each has
`flagged: true`, `flag_reason: "billing anomaly; see ticket t019"`).

Ticket `t019` is an escalated, critical-priority ticket from her with
subject "billing broken since the weekend" and a body that names the three
order ids explicitly. It is the canonical entry point for her story.

---

## A16 -- runbook link is indirect

The full writeup of the `pipe-07` partial-failure incident lives at
`/runbook/incident-42`. It is linked from `/docs/troubleshooting` at the
bottom ("Related reading") and from `/runbook/backfill` -- but it is NOT
referenced from any `pipe-07` fixture or from the CLI's own
`ctl pipeline status pipe-07` output. An agent has to discover it by
reading docs/runbooks.

The page lists:
- Exact date and time of the failure (`2026-04-18T14:42:09Z`)
- The 147/200 split
- The collateral refunds (`o088`, `o091`) and their owning user (`u017`)
- The `--resume` and `--rollback` recovery options
- The search-index-stale consequence

---

## A17 -- `pipe-04` skipped records

`ctl pipeline run pipe-04` (name: `backfill-products`) exits `0` and
prints to stderr:

    Warning: 2 records skipped (see /tmp/pipe-04.skipped)

The file `/tmp/pipe-04.skipped` is written with the two skipped product
ids, one per line: `p044`, `p077`.

Why they were skipped lives on the product fixtures themselves, in a
`pipe_04_skip_reason` field:

| product | reason                                     |
|---------|--------------------------------------------|
| p044    | missing SKU prefix (legacy import)         |
| p077    | price_cents null in source feed            |

---

## A18 -- NULL emails on `u023`, `u031`, `u049`

Three users have `"email": null`. A naive "find this email" search that
calls `.lower()` on every row's `email` field will crash on these users.
`ctl search` is null-safe (it skips null fields outright), but
user-written post-processing often is not.

**Trigger:**
```
ctl get users u023 --format json      # email: null
ctl get users u031 --format json      # email: null
ctl get users u049 --format json      # email: null
```
