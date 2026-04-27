---
name: pipeline-prerequisites
description: Use when a pipeline (notably `pipe-05` / `reindex-search`) exits 2 with stderr `prerequisite not met`. The CLI does not name the prereq; pipe-05 needs pipe-03 to have run in the current state dir.
---

# Pipeline prerequisites

Some pipelines depend on another pipeline having run earlier in the
current state dir. The CLI tracks this via marker files under
`$CTL_STATE_DIR` (default `~/.ctl-state/`) and refuses with
`prerequisite not met` (exit 2) if the marker is missing. It does NOT
disclose which pipeline is the prereq.

## Known prerequisite

- `pipe-05` (`reindex-search`) requires `pipe-03` (`rotate-keys`) to have
  run in the current state dir. The marker is
  `$CTL_STATE_DIR/pipe-03_ran.json`.

Wiping the state dir resets the marker, so `pipe-05` will refuse again.

## Wrong invocation

```sh
$ rm -rf ~/.ctl-state
$ ctl pipeline run pipe-05
prerequisite not met
$ echo $?
2
```

## Right invocation

```sh
$ ctl pipeline run pipe-03
pipeline rotate-keys: ok
$ ctl pipeline run pipe-05
pipeline reindex-search: ok
```

## Common mistakes

- Re-running pipe-05 with different flags hoping one sticks. None will;
  the prereq is a marker file.
- Wiping `~/.ctl-state` mid-task to "start fresh" between pipe-03 and
  pipe-05 -- you just deleted the marker. To clear pages or search
  caches between steps, prefer `ctl cache clear pages` /
  `ctl cache clear search` over a whole-dir wipe.

## Side effect to know about

Running `pipe-03` ALSO marks the `/docs/*` page cache stale (see
`clear-cache-after-pipe03`). After this sequence you may need
`ctl cache clear` before fetching docs.
