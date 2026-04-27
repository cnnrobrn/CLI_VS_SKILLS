---
name: handle-null-emails
description: "Use when post-processing user records by email (e.g. lowercasing, regex). Three users have null emails (u023, u031, u049); naive `.lower()` on every row will AttributeError. Filter for null first."
---

# Null emails on u023, u031, u049

Three user records ship with `"email": null`:

- `u023`
- `u031`
- `u049`

`ctl search` is null-safe (it skips null fields outright), so a
search-side filter is fine. User-written post-processing usually is
not.

## Wrong invocation

```python
users = json.loads(subprocess.check_output(
    ["ctl", "list", "users", "--limit", "1000", "--format", "json"]))
emails = [u["email"].lower() for u in users]
# AttributeError: 'NoneType' object has no attribute 'lower'
```

## Right invocations

`jq` filter:

```sh
ctl list users --limit 1000 --format json \
  | jq '.[] | select(.email != null)'
```

Python:

```python
emails = [u["email"].lower() for u in users if u.get("email")]
```

For an email-by-email search, prefer `ctl search`:

```sh
ctl search --query "@acme.io" --scope users --i --format json
```

## Common mistakes

- Crashing partway through a script and not noticing that some rows
  were silently dropped from a partial result.
- Treating "no email" as "missing data" -- the null is intentional
  fixture state, not a bug.
