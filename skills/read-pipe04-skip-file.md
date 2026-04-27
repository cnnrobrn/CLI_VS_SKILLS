---
name: read-pipe04-skip-file
description: Use after running `pipe-04` (`backfill-products`). It exits 0 with a stderr warning that 2 records were skipped to `/tmp/pipe-04.skipped`. The skipped ids are `p044` and `p077`; their skip reasons live on the product fixtures themselves.
---

# `pipe-04` writes a skipped-records file

`ctl pipeline run pipe-04` (`backfill-products`) exits 0 even when it
skips records. The only signal is a stderr warning:

```
Warning: 2 records skipped (see /tmp/pipe-04.skipped)
```

If you don't read stderr, you'll miss this entirely.

## Right invocation

```sh
$ ctl pipeline run pipe-04
[1/3] fetch-feed: 82 rows
[2/3] backfill: 80 rows
[3/3] index: ok
pipeline backfill-products: ok
# stderr: Warning: 2 records skipped (see /tmp/pipe-04.skipped)

$ cat /tmp/pipe-04.skipped
p044
p077
```

## Why each was skipped

The reason for each skip is on the product record itself, in a
`pipe_04_skip_reason` field:

| product | reason                                  |
|---------|-----------------------------------------|
| p044    | missing SKU prefix (legacy import)      |
| p077    | price_cents null in source feed         |

Pull the fixtures to confirm:

```sh
ctl get products p044 --format json   # pipe_04_skip_reason: missing SKU prefix...
ctl get products p077 --format json   # pipe_04_skip_reason: price_cents null...
```

## Common mistakes

- Treating the exit-0 + "ok" as "all records loaded." Always grep
  stderr for `skipped`.
- Assuming the skip file lives under `~/.ctl-state/`. It is in
  `/tmp/pipe-04.skipped`.
- Only reading the skip file (which gives just ids). The reasons are
  on the product fixtures, not in the skip file itself.
