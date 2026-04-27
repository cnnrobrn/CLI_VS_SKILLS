---
name: discover-runbooks
description: Use when investigating any incident, pipeline failure, or cross-resource anomaly. The canonical writeups live under `/runbook/*` and `/help/*` -- they are NOT linked from CLI output. Fetch the right one to short-circuit hours of investigation.
---

# Runbooks are the connective tissue

The CLI does NOT link to runbooks from its own output. `ctl pipeline
status pipe-07` will not tell you `/runbook/incident-42` exists, even
though that page contains the entire writeup. You have to discover
runbooks by reading docs.

## The pages worth knowing

| page                       | what it covers                                          |
|----------------------------|---------------------------------------------------------|
| `/docs/troubleshooting`    | canonical "something is off" index; links to runbooks   |
| `/runbook/incident-42`     | pipe-07 partial-apply writeup: date, 147/200, o088/o091 collateral, --resume vs --rollback |
| `/runbook/reconcile`       | why pipe-09 needs `--verify`                            |
| `/runbook/backfill`        | how to pick `--resume` vs `--rollback`                  |
| `/runbook/rotate-keys`     | calls out the page-cache side effect of pipe-03         |
| `/help/duplicates`         | the triple-submit convention                            |
| `/help/refunds`            | refund statuses and `refund_source` semantics           |

Note: runbooks and help pages are NOT affected by the post-pipe-03
page-cache stale (see `clear-cache-after-pipe03`). Only `/docs/*`
slugs are affected by that, plus the default-state `/docs/auth`
404 (see `clear-stale-page-cache`).

## How to use

Start any non-trivial investigation by fetching `/docs/troubleshooting`
and following the "Related reading" links. For pipeline-specific
incidents, also fetch the matching runbook directly.

```sh
ctl fetch /docs/troubleshooting
ctl fetch /runbook/incident-42
```

If `/docs/*` returns a 404, see `clear-stale-page-cache` or
`clear-cache-after-pipe03`.

## Common mistakes

- Investigating pipe-07 from `ctl pipeline status` alone. The status
  output is correct but minimal; the runbook explains the *why*.
- Trying `--help` for incident context. `--help` documents flags, not
  incidents.
