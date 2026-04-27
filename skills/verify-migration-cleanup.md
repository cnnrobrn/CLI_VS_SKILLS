---
name: verify-migration-cleanup
description: "Recipe for 'did the migration finish cleanly?' tasks. Pre/post count idiom — capture row counts before, run the pipeline with verification flags, capture counts after, diff. Anchored on pipe-09 reconcile-inventory."
---

# Recipe: Verify a migration finished cleanly

Scenario: "did `reconcile-inventory` actually reconcile anything, or
did it just print OK?"

The general pattern: pipelines that write data exit 0 whether or not
they did the job. Trust comes from explicit verification, not from
exit codes. This recipe shows the canonical idiom on `pipe-09`.

## Steps

### 1. Capture pre-state

```sh
ctl list products --limit 1000 --format json \
  | jq '[.[] | select(.inventory_discrepancy != null)] | length'
```

For pipe-09 this is `3` (products `p014`, `p037`, `p061`).

### 2. Run the pipeline WITH verification

A bare `ctl pipeline run pipe-09` is cosmetic (see
`verify-reconcile-inventory`). Use `--verify`:

```sh
ctl pipeline run pipe-09 --verify
# pipeline reconcile-inventory: ok, verified: true, discrepancies: 3
```

### 3. Pull the discrepant records

```sh
for p in p014 p037 p061; do
  ctl get products "$p" --format json
done
```

Each carries an `inventory_discrepancy` block:

| product | recorded | warehouse | delta |
|---------|--------:|---------:|-----:|
| p014    |     120 |      117 |   -3 |
| p037    |      42 |       50 |   +8 |
| p061    |       0 |        5 |   +5 |

### 4. Confirm the post-state

```sh
ctl pipeline status pipe-09
```

If `--verify` reported `discrepancies: 0`, the recorded inventory is
authoritative. If more than 3, fixture state has drifted; wipe
`~/.ctl-state` and re-run (mind `pipeline-prerequisites` if pipe-05
was in your chain).

## Generalising

For any migration:

1. Snapshot the relevant counts and ids beforehand.
2. Run the pipeline with whatever verification flag exists
   (`--verify`, `--check`, `--dry-run` if available).
3. Re-snapshot.
4. Diff.

Always pass `--limit 1000 --format json` on the snapshot queries (see
`paginate-list-results`, `format-output-fidelity`).

## Common mistakes

- Reporting "migration ok" from a bare `pipe-09` run.
- Snapshotting counts at default `--limit 10` and concluding nothing
  changed.
- Skipping the `ctl pipeline status` cross-check at the end.
