---
name: find-flagged-records
description: "Recipe for 'find all flagged X for user Y' tasks. Filter chain — search/list to find user id, then `ctl list orders --limit 1000 --format json | jq` to filter by user_id AND flagged==true. Anchored on Sarah Chen."
---

# Recipe: Find all flagged records for a user

Scenario: "find the flagged orders for Sarah Chen."

This is the canonical filter-chain task: name -> id, then list ->
filter by id + flag. The trap is doing it without `--limit 1000`.

## Steps

### 1. Resolve the name to an id

```sh
rm -rf ~/.ctl-state
ctl search --query "sarah.chen" --scope users --i --format json
# -> u042
```

`--i` matters here -- see `case-insensitive-search`. If you don't
know the email, search by last name with `--i`.

### 2. Confirm the user

```sh
ctl get users u042 --format json
# -> status: suspended, status_changed_at: 2026-04-22T11:47:00Z
```

The suspended status is part of her story (see
`handle-suspended-account`).

### 3. Filter orders by user_id AND flagged

```sh
ctl list orders --limit 1000 --format json \
  | jq '[.[] | select(.user_id=="u042" and .flagged==true)] | map(.id)'
# -> ["o102", "o107", "o115"]
```

`--limit 1000` is critical. With the default 10, you would miss most
of her orders entirely.

### 4. Cross-reference the ticket

```sh
ctl get tickets t019 --format json
# escalated, critical, subject "billing broken since the weekend"
# body explicitly names o102, o107, o115
```

`t019` is the canonical entry point for her story.

## Generalising

For any "flagged X for user Y" task:

1. Resolve Y -> id via `ctl search --i`.
2. Confirm with `ctl get`.
3. `ctl list X --limit 1000 --format json | jq` filtering on
   `user_id` and any flag field.
4. Look for a related ticket (escalated/critical) -- it usually
   references the records by id in its body.

## Common mistakes

- Starting from `ctl list tickets` and trying to walk to orders. The
  body of `t019` mentions the order ids, but only after you know to
  pull it. The user-first chain is more direct.
- Forgetting `--limit 1000` and getting an empty filter result that
  is really a pagination artifact.
- Forgetting `--i` on the search and getting zero hits.
