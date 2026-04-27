---
name: cross-check-list-and-search
description: Recipe -- use whenever you need to trust a row count after a pipeline ran. Cross-check `ctl list --status X` against `ctl search --query "status:X"`; if they disagree, the search index is stale and `ctl search --reindex` is the fix.
---

# Recipe: Cross-check list and search to detect index drift

Two sources of truth, one fixture state:

- `ctl list <resource> --status X` reads underlying records directly.
- `ctl search --query "status:X" --scope <resource>` reads through
  the search index.

If they disagree, the search index is stale. The most common cause
is `pipe-07` having run with `--resume` or `--rollback` (see
`reindex-stale-search`), but any pipeline that touches order status
can do it.

## Steps

### 1. Run both queries

```sh
ctl list   orders --status paid --limit 1000 --format json | jq 'length'
ctl search --query "status:paid" --scope orders | jq 'length'
```

`--limit 1000` matters on the list side (see
`paginate-list-results`).

### 2. Compare

If they match: trust the count.

If they differ -- typically by exactly two rows after a pipe-07
action, with `o088` and `o091` as the offenders:

### 3. Reindex and re-cross-check

```sh
ctl search --reindex
ctl search --query "status:paid" --scope orders | jq 'length'
# now matches ctl list
```

## Use this whenever

- A status filter materially affects the answer.
- A pipeline ran in the current session (especially pipe-07).
- Two queries that should logically agree disagree by 1-3 rows.

## Common mistakes

- Trusting whichever number "feels right." Reindex and re-check.
- Reindexing without also re-running the queries -- you need to
  confirm the disagreement is gone.
- Confusing this with the `--limit` trap. Pagination differences
  are 100+ rows; index drift is typically 1-3 rows.
