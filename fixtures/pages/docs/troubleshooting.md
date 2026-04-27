# Troubleshooting

- `not found`: wrong id, or wrong resource for the id (e.g. `ctl get users o001`).
- `refused`: a pipeline wants `--confirm`. Check the corresponding runbook.
- `prerequisite not met`: another pipeline must have run first in this session.
- `invalid date`: see /docs/dates for accepted shapes.
- Stale data after pipelines: run `ctl cache clear` and
  `ctl search --reindex`.

Related reading:
- /runbook/incident-42 -- the canonical writeup of the pipe-07 partial.
- /runbook/deploy
- /runbook/backfill
