---
name: clear-cache-after-pipe03
description: Use when `ctl fetch /docs/*` returns a canned 404 immediately after running `pipe-03` (`rotate-keys`). The page cache is marked stale; `ctl cache clear` (or `ctl cache clear pages`) restores the real pages.
---

# Page cache stale after pipe-03

Running `pipe-03` (`rotate-keys`) marks the `/docs/*` page cache stale.
Every subsequent `ctl fetch /docs/<slug>` returns the canned 404 body
(see `fixtures/pages/_stale_404.md`) until the cache is cleared.

Slugs outside `/docs/*` (e.g. `/runbook/*`, `/help/*`) are unaffected.
This is distinct from the default-state `/docs/auth` 404 (see
`clear-stale-page-cache`).

## Wrong invocation

```sh
$ ctl fetch /docs/pagination | head -1
# Pagination
$ ctl pipeline run pipe-03
pipeline rotate-keys: ok
$ ctl fetch /docs/pagination | head -1
# 404 Not Found        # exit 0 -- silent
```

The 404 body itself contains the diagnostic ("page cache is stale; run
`ctl cache clear`"), but only if you actually read it.

## Right invocation

```sh
$ ctl cache clear
cleared ... (all)
$ ctl fetch /docs/pagination | head -1
# Pagination
```

`ctl cache clear pages` works too and is more surgical -- it leaves
pipeline run markers (e.g. the pipe-03 marker that pipe-05 needs) intact.

## Common mistakes

- Concluding "the doc was deleted" from the 404. Read the body.
- Running `rm -rf ~/.ctl-state` to fix the cache. That works, but it
  also deletes the `pipe-03_ran.json` marker that `pipe-05` requires --
  see `pipeline-prerequisites`.
