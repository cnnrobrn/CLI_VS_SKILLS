---
name: diff-resource-type-validation
description: Use when `ctl diff a b` returns `{}` and exits 0. Empty object does NOT mean "identical"; it means you passed ids of different resource types (e.g. `u001` vs `o001`) and the CLI swallowed it. Always diff within the same resource.
---

# Diff across resource types is silently empty

`ctl diff` does not validate that both ids belong to the same resource.
When they don't, it prints `{}` and exits 0 -- which looks exactly like
"these are identical."

## Wrong invocation

```sh
$ ctl diff u001 o001
{}
$ echo $?
0
```

## Right invocation

```sh
$ ctl diff u001 u002
{
  "only_in_a": {...},
  "only_in_b": {...},
  "changed": { ... }
}
```

## Rule of thumb

Before calling `ctl diff a b`, confirm that `a` and `b` share a resource
prefix:

- `u<NNN>` -> users
- `o<NNN>` -> orders
- `t<NNN>` -> tickets
- `p<NNN>` -> products
- `s<NNN>` -> sessions

If the prefixes differ, the diff is meaningless. Restate the question.

## Common mistakes

- Reporting "user u001 and order o001 are identical" because the diff
  was empty.
- Diffing a user against a ticket in the same id namespace by mistake
  -- always check the prefix.
