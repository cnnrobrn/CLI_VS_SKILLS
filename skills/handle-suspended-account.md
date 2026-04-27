---
name: handle-suspended-account
description: Use when investigating Sarah Chen (`u042`) or any "account flipped to suspended" billing escalation. Her account suspended on 2026-04-22; flagged orders are `o102`, `o107`, `o115`; ticket `t019` is the canonical entry point.
---

# Sarah Chen (u042) and the billing escalation

Sarah Chen is the canonical suspended-account investigation. Her
account flipped to `suspended` on `2026-04-22T11:47:00Z` pending
billing-dispute review.

## The key facts

| field             | value                                                        |
|-------------------|--------------------------------------------------------------|
| id                | u042                                                         |
| email             | sarah.chen@acme.io                                           |
| name              | Sarah Chen                                                   |
| status            | suspended                                                    |
| status_changed_at | 2026-04-22T11:47:00Z                                         |
| org_id            | org-2                                                        |
| notes             | billing dispute; account flipped to suspended pending review |

She has 3 flagged orders: `o102`, `o107`, `o115`. Each has
`flagged: true` and `flag_reason: "billing anomaly; see ticket t019"`.

Ticket `t019` is escalated, critical priority, subject "billing broken
since the weekend." Its body names the three order ids explicitly.
`t019` is the canonical entry point for her story.

## Right investigation chain

```sh
# 1. Find her id
ctl search --query "sarah.chen" --scope users --i --format json
# -> u042

# 2. Pull the user record
ctl get users u042 --format json
# -> status: suspended, status_changed_at: 2026-04-22T11:47:00Z

# 3. Pull her flagged orders (need --limit 1000, see paginate-list-results)
ctl list orders --limit 1000 --format json \
  | jq '[.[] | select(.user_id=="u042" and .flagged==true)] | map(.id)'
# -> ["o102", "o107", "o115"]

# 4. The escalation ticket
ctl get tickets t019 --format json
# -> escalated, critical, names o102/o107/o115
```

## Wrong invocations

- `ctl list tickets` without `--limit 1000` may not include `t019`
  (see `paginate-list-results`).
- `ctl search --query sarah.chen` (no `--i`) may miss her if
  case-sensitive matching kicks in (see `case-insensitive-search`).
- Trying to look her up via the tickets list first as a primary path
  -- the body mentions the order ids but only after you know to pull
  it, and the chain via `users` is more direct.

## Common mistakes

- Confusing her flagged-but-paid orders with refunds. None of
  `o102`/`o107`/`o115` is refunded.
- Confusing her with `u017` (whose collateral refunds are pipe-07
  damage; see `recover-pipe07-partial`).
