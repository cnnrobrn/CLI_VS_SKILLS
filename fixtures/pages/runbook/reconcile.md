# Runbook: Reconcile Inventory

`ctl pipeline run reconcile-inventory` exits 0 with `status: ok` by
default. That output is untrustworthy -- it does not actually verify
anything unless you pass `--verify`, which emits the discrepancy list
and an accurate summary. Always pass `--verify` for audits.
