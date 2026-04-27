# Runbook: Deploy

`ctl pipeline run deploy-prod` requires `--confirm`. Without the flag the
pipeline prints `refused` to stderr and exits 2. This is by design.
