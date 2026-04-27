---
name: recover-pipe07-partial
description: Use when working with `pipe-07` (`backfill-orders`). The fixture state is pre-baked as 147/200 partial; a bare `ctl pipeline run pipe-07` is an idempotent no-op. To advance, choose `--resume` (finish 53) or `--rollback` (revert 147).
---

# Recovering pipe-07 from partial state

`pipe-07` (`backfill-orders`) ships in a partial state: 147 of 200
records applied, failure recorded at `2026-04-18T14:42:09Z`, with
collateral refunds on `o088` and `o091` (both owned by `u017`).

A bare `ctl pipeline run pipe-07` prints the current status and exits
0 -- it is a safe no-op intended for inspection. To make progress you
must explicitly choose:

- `--resume` -> apply the remaining 53, end at 200/200, state
  `complete`.
- `--rollback` -> undo the 147 already applied, end at 0/200, state
  `rolled_back`.

Either choice marks the search index stale (see `reindex-stale-search`).

## Inspect first

```sh
$ ctl pipeline status pipe-07
pipeline: backfill-orders (pipe-07)
completed: 147/200, remaining: 53, state: partial
failed_at: 2026-04-18T14:42:09Z
collateral_refunds: o088, o091
```

## Wrong invocations

```sh
$ ctl pipeline run pipe-07
# prints status, exits 0 -- no progress made
$ ctl pipeline run pipe-07 --confirm
# --confirm is for pipe-01/pipe-06, not pipe-07. Still a no-op here.
```

## Right invocations

```sh
# Finish the work
ctl pipeline run pipe-07 --resume
ctl pipeline status pipe-07     # completed: 200/200, state: complete
ctl search --reindex            # search index was marked stale

# Or undo
ctl pipeline run pipe-07 --rollback
ctl pipeline status pipe-07     # completed: 0/200, state: rolled_back
ctl search --reindex
```

## Common mistakes

- Treating the bare-run exit-0 as "the pipeline ran." It did not. Read
  the status line.
- Skipping `ctl search --reindex` afterwards and getting two-row
  disagreements between `list` and `search` on `o088`/`o091`.
- Forgetting that `--resume` versus `--rollback` is a real product
  decision -- `/runbook/incident-42` and `/runbook/backfill` describe
  the trade-off.
