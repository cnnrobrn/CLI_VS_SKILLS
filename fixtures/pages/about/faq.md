# FAQ

Q: Why does `ctl list users` only show 10 rows?
A: Default limit is 10. Pass `--limit 100` or higher.

Q: Why does `ctl search --query acme` find nothing?
A: Search is case-sensitive by default. Try `--query Acme` or pass `--i`.

Q: Why does `ctl diff u001 o001` return `{}`?
A: Cross-resource diffs silently produce an empty object. Compare ids
   from the same resource.

Q: What does the `refused` exit mean?
A: The pipeline wants `--confirm`. See the relevant runbook.
