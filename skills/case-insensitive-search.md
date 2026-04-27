---
name: case-insensitive-search
description: Use when `ctl search --query <q>` returns zero results for a brand or term you expect to exist. Search is case-sensitive by default; pass `--i` or match the actual case (e.g. `Acme`, not `acme`).
---

# Case-sensitive search

`ctl search --query Q` does exact substring matching without case
folding. A lowercase brand search against capitalised data returns `[]`.
Treat this as a design fact about the CLI, not a transient bug.

## The canonical example

| query        | scope=products | result   |
|--------------|---------------:|----------|
| `acme`       | products       | 0 rows   |
| `Acme`       | products       | 12 rows  |
| `acme --i`   | products       | 12 rows  |

The 12 Acme products are: "Acme Foghorn", "Acme Anvil", "Acme Rocket
Skates", "Acme Earthquake Pills" (plus `Mk 1` and `Mk 2` variants).

## Wrong invocation

```sh
$ ctl search --query acme --scope products | jq 'length'
0
```

## Right invocations

```sh
ctl search --query Acme --scope products | jq 'length'        # 12
ctl search --query acme --scope products --i | jq 'length'    # 12
```

For field-filter syntax, `--i` still applies:

```sh
ctl search --query "status:paid" --scope orders --i
```

## Common mistakes

- Concluding "the brand isn't in the catalog" from a zero-row search.
- Trying regex syntax to dodge case. `ctl search` does not support
  regex; the right answer is `--i`.
