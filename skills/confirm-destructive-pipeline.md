---
name: confirm-destructive-pipeline
description: Use when `ctl pipeline run pipe-01` (deploy-prod) or `pipe-06` (purge-audit-logs) exits 2 with a bare `refused` on stderr. The CLI gives no hint, but `--confirm` is the fix for both.
---

# Destructive pipeline refusal

Two pipelines refuse to run without `--confirm`:

- `pipe-01` (`deploy-prod`)
- `pipe-06` (`purge-audit-logs`)

Both exit `2` with stderr of exactly `refused`. The CLI never tells you
that `--confirm` is the missing piece.

## Wrong invocation

```sh
$ ctl pipeline run pipe-01
refused
$ echo $?
2
```

## Right invocation

```sh
$ ctl pipeline run pipe-01 --confirm
[1/4] build: ok
...
pipeline deploy-prod: ok
$ echo $?
0
```

Same shape for `pipe-06`:

```sh
ctl pipeline run pipe-06 --confirm
```

## Common mistakes

- Treating `refused` as "the pipeline is broken" and escalating.
- Looking for the missing flag in `--help` (it's listed, but the error
  itself says nothing about it).
- Adding `--confirm` to non-destructive pipelines like `pipe-02` --
  harmless, but unnecessary.

Use this skill only when you actually intend the destructive operation.
For `pipe-01` that is a real prod deploy; for `pipe-06` it permanently
deletes audit logs.
