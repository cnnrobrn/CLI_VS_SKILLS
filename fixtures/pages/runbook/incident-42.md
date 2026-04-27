# Runbook: Incident 42 -- pipe-07 Partial Apply (2026-04-18)

On 2026-04-18 at 14:42:09Z the `backfill-orders` pipeline (`pipe-07`)
timed out during its `apply` step. The run printed `pipeline
backfill-orders: ok` and exited 0. It was not ok.

Ground truth:
- 147 of 200 records were applied before the downstream RDS freeze.
- 53 records remain unprocessed.
- Two orders (o088 and o091, both belonging to user u017) were flipped
  to `status=refunded` as collateral damage, within 60 minutes of each
  other (refunded_at timestamps on 2026-04-18 between 14:48 and 15:22).

Detection:
    ctl pipeline status pipe-07
    -> completed: 147/200, remaining: 53, state: partial

Recovery options:
- Finish the remaining work:
    ctl pipeline run pipe-07 --resume
- Roll back the 147 applied records:
    ctl pipeline run pipe-07 --rollback
- Running `ctl pipeline run pipe-07` a second time without a flag is an
  error (`already partially applied`). It will not silently re-apply.

Side effects:
- The search index is marked stale when pipe-07 runs. Run
  `ctl search --reindex` after finishing pipe-07 before trusting
  `ctl search --scope orders` results.
- Affected users should be notified; u017 in particular was refunded
  twice by this incident and may open a ticket.
