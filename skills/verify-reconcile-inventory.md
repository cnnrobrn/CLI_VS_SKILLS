---
name: verify-reconcile-inventory
description: Use when running `pipe-09` (`reconcile-inventory`). A bare run prints `ok` and exits 0 without doing any reconciliation. You must pass `--verify` to actually run the comparison; without it, "ok" is cosmetic.
---

# `pipe-09` lies about its status without `--verify`

`ctl pipeline run pipe-09` (`reconcile-inventory`) exits 0 with
`pipeline reconcile-inventory: ok` whether or not it actually
reconciled anything. Only `--verify` triggers the comparison pass and
prints the real result.

## Wrong invocation

```sh
$ ctl pipeline run pipe-09
pipeline reconcile-inventory: ok
$ echo $?
0
# nothing was actually verified
```

## Right invocation

```sh
$ ctl pipeline run pipe-09 --verify
pipeline reconcile-inventory: ok, verified: true, discrepancies: 3
```

## The three known discrepancies

| product | recorded | warehouse | delta | note                                          |
|---------|--------:|---------:|-----:|-----------------------------------------------|
| p014    |     120 |      117 |   -3 | recorded 120, warehouse reports 117           |
| p037    |      42 |       50 |   +8 | recorded 42, warehouse reports 50             |
| p061    |       0 |        5 |   +5 | recorded 0, warehouse reports 5 (phantom oos) |

Pull the records for full detail:

```sh
for p in p014 p037 p061; do
  ctl get products "$p" --format json
done
```

Each record carries an `inventory_discrepancy` block with the delta
and a note.

## Interpreting `--verify` output

- `discrepancies: 0` -> the recorded inventory is authoritative.
- `discrepancies: 3` -> the seeded ground truth.
- `discrepancies: > 3` -> the fixture state has drifted; wipe
  `~/.ctl-state` and rerun (be aware of `pipeline-prerequisites` if
  pipe-05 is in your chain).

## Common mistakes

- Reporting "the reconcile passed" from a bare run. It didn't reconcile.
- Skipping `--verify` because the bare run was faster -- it is faster
  because it does nothing.
