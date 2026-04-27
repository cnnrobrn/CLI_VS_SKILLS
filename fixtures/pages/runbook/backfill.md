# Runbook: Backfill

The `backfill-orders` pipeline (pipe-07) is NOT safe to blind-re-run
after a partial apply. See /runbook/incident-42. Choose explicitly
between `--resume` and `--rollback`.
