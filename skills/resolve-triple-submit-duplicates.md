---
name: resolve-triple-submit-duplicates
description: "Use when investigating duplicate orders — three orders with the same user_id, same total_cents, and timestamps a few seconds apart. Convention from /help/duplicates — keep the lowest id paid, refund the others."
---

# Triple-submit duplicate orders

A "triple-submit" is three orders from the same user, with identical
`total_cents`, and `created_at` timestamps a few seconds apart. The
fixture set holds one such triple:

| id   | user | total_cents | created_at                |
|------|------|------------:|---------------------------|
| o067 | u008 |        4999 | 2026-04-10T08:12:15Z      |
| o068 | u008 |        4999 | 2026-04-10T08:12:16Z      |
| o069 | u008 |        4999 | 2026-04-10T08:12:17Z      |

Already applied per convention: `o067` is `paid`, `o068` and `o069`
are `refunded` with `refund_reason: "duplicate submission
(triple-submit)"`.

## The convention (from `/help/duplicates`)

When you see a triple-submit:

1. Keep the **lowest id** as `paid`.
2. Refund the other two with
   `refund_reason = "duplicate submission (triple-submit)"`.

If you encounter a new triple elsewhere in a task, apply the same rule.

## How to detect

```sh
ctl list orders --limit 1000 --format json \
  | jq 'group_by(.user_id + "|" + (.total_cents|tostring))
        | map(select(length >= 3))
        | .[]
        | sort_by(.created_at)'
```

A cluster of 3 with `created_at` diffs in seconds is a triple-submit.
Verify before assuming -- legitimate same-cart-different-skus orders
also exist.

## Wrong invocation

- Refunding all three. Customer paid once -- one of the three should
  remain `paid`.
- Refunding the lowest id. Convention is to keep it.

## Right invocation (already applied; confirm only)

```sh
ctl get orders o067 --format json   # status: paid
ctl get orders o068 --format json   # status: refunded, reason as above
ctl get orders o069 --format json   # status: refunded, reason as above
```

## Common mistakes

- Treating the two refunds as a customer-driven refund event. They are
  duplicate-submission corrections.
- Confusing this with the `pipe-07` collateral refunds on `o088`/`o091`
  (different cause; see `recover-pipe07-partial`).
