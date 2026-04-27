---
name: clear-stale-page-cache
description: "Use when `ctl fetch /docs/auth` returns a 404 on fresh state. The default for that page is a stale-cache 404; `ctl cache clear` repairs it. Distinct from the post-pipe-03 stale."
---

# Default-state 404 on /docs/auth

Unlike the post-pipe-03 cache stale (which only kicks in after pipe-03
runs and affects all `/docs/*`), the `/docs/auth` page returns the
canned 404 body by default -- before any pipeline has run. This
simulates a stale cache entry that ships with the CLI's initial state.

## Wrong invocation

```sh
$ rm -rf ~/.ctl-state
$ ctl fetch /docs/auth
# 404 Not Found
# ...page cache is stale; run `ctl cache clear`...
```

The body itself names the fix, but only if you actually read it. Exit
code is 0.

## Right invocation

```sh
$ ctl cache clear
cleared ... (all)
$ ctl fetch /docs/auth
# Authentication       # the real page
```

`ctl cache clear pages` is the surgical equivalent. A fresh wipe of
`$CTL_STATE_DIR` puts the anomaly back: the next `ctl fetch /docs/auth`
will 404 again.

## How to tell the two doc-cache anomalies apart

- `/docs/auth` 404 from the start, before any pipeline -> this skill.
- ALL `/docs/*` 404 immediately after `pipe-03` ran -> see
  `clear-cache-after-pipe03`.

The fix is the same (`ctl cache clear`); the trigger is different.

## Common mistakes

- Treating a 404 as "the doc doesn't exist" without reading the body.
- Wiping the state dir to fix the cache and breaking other markers.
