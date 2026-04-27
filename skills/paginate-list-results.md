---
name: paginate-list-results
description: Use when running `ctl list <resource>` to count records or filter to "all" of something. The default `--limit` is 10 and silently truncates with no warning, so any cardinality answer derived from the default page is almost certainly wrong.
---

# Pagination

`ctl list` returns at most 10 rows by default. There is no `truncated`
banner, no stderr warning, and no `--count` flag. If your answer depends
on "how many" or "show me all," you must override `--limit`.

## True row counts

| resource | rows |
|----------|----:|
| users    |  50 |
| orders   | 120 |
| tickets  |  30 |
| products |  80 |
| sessions |  15 |

Only `sessions` fits inside the default page.

## Wrong invocation

```sh
ctl list orders | wc -l
# 12  (10 data rows + header + separator)  -- conclude "10 orders"
```

## Right invocation

```sh
ctl list orders --limit 1000 --format json | jq 'length'
# 120
```

`--limit 1000` is the safe ceiling for every fixture in this CLI.

## How to detect truncation

- If `len(results) == 10` and you did not pass `--limit`, you almost
  certainly hit the default. Re-run with a higher limit before drawing
  conclusions.
- `--format table` and counting visible rows is the same trap.
- A non-integer to `--limit` fails with `--limit must be an integer`
  (no examples). Pass an integer.

## Common mistakes

- Concluding "u017 has 10 orders" from a default `ctl list orders` run.
  u017 actually has 14 orders.
- Running `ctl list orders | grep refunded | wc -l` and reporting a
  refund total. The grep ran over only the first 10 rows.
- Eyeballing a default-paged table and inferring totals.
