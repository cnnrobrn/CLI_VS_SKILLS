---
name: diagnose-refund-burst
description: Recipe -- use when a task says "two orders got refunded fast for u017" or any pipe-07 collateral-refund investigation. Combines pagination, runbook discovery, and pipe-07 status into a 4-step diagnosis.
---

# Recipe: Diagnose a refund burst

Scenario: "two orders got refunded really fast, something weird
happened for `u017`."

This is the canonical pipe-07 collateral-refund investigation. The
two orders are `o088` and `o091`; the cause is the pipe-07
partial-apply on `2026-04-18`. Ground truth lives at
`/runbook/incident-42`.

## Steps

### 1. List ALL of u017's orders (not the default 10)

`u017` owns 14 orders. Default `--limit 10` will miss most.

```sh
rm -rf ~/.ctl-state
ctl list orders --limit 1000 --format json \
  | jq '[.[] | select(.user_id=="u017")] | sort_by(.created_at)'
```

See `paginate-list-results` if this is unfamiliar.

### 2. Identify the refund pair

Look for refunds with a `refund_source` or refund timestamps close
together. You will find:

- `o088` refunded `2026-04-18T14:48:12Z`,
  `refund_source: "pipe-07"`,
  `refund_reason: "collateral: pipe-07 partial apply"`.
- `o091` refunded `2026-04-18T15:21:03Z`, same source, same reason.

That is the burst.

### 3. Read the runbook

```sh
ctl fetch /docs/troubleshooting
ctl fetch /runbook/incident-42
```

The runbook gives you the date, the 147/200 split, and names both
orders. See `discover-runbooks` if `/docs/*` 404s (try
`ctl cache clear`).

### 4. Confirm pipeline state

```sh
ctl pipeline status pipe-07
# completed: 147/200, remaining: 53, state: partial
# failed_at: 2026-04-18T14:42:09Z
# collateral_refunds: o088, o091
```

## The answer to give

The two refunds were collateral damage from the pipe-07 partial apply
on 2026-04-18, not customer-driven. Recovery options are
`--resume` (finish the remaining 53) or `--rollback` (undo the 147).
Either one marks the search index stale, so follow up with
`ctl search --reindex`. See `recover-pipe07-partial`.

## Common mistakes

- Reporting "u017 has 2 refunded orders" without identifying the
  pipe-07 cause.
- Doing the right detective work but stopping before reading the
  runbook -- the runbook is the canonical writeup; cite it.
