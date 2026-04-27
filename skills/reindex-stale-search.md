---
name: reindex-stale-search
description: Use when `ctl search` and `ctl list` disagree on the same filter (notably `status:paid` on orders) after running `pipe-07 --resume` or `--rollback`. The search index is marked stale; `ctl search --reindex` resyncs it.
---

# Stale search index after pipe-07

Any `pipe-07` action (`--resume` or `--rollback`) marks the search
index stale. Until you reindex, faceted search results disagree with
`ctl list` on at least two specific orders: `o088` and `o091`.

- `ctl list` reflects the underlying fixture state (both `refunded`).
- `ctl search` with the stale index still reports them `paid`.

## Wrong invocation

```sh
$ ctl pipeline run pipe-07 --resume
$ ctl list   orders --status paid --limit 1000 --format json | jq 'length'
36
$ ctl search --query "status:paid" --scope orders | jq 'length'
38      # search still sees o088, o091 as paid
```

## Right invocation

```sh
$ ctl search --reindex
search index rebuilt
$ ctl search --query "status:paid" --scope orders | jq 'length'
36
```

## Rule of thumb

Any time a `pipe-07` action happens in this session, run
`ctl search --reindex` before trusting search faceted results on orders.
If two queries that should agree disagree by exactly two rows, suspect a
stale index first.

## Common mistakes

- Reporting the search count when the list count would have been right.
- Reindexing without first running pipe-07 -- harmless, but a noop.
- Wiping the state dir to "fix" the inconsistency. That fixes nothing
  and may reset other markers (see `pipeline-prerequisites`).
