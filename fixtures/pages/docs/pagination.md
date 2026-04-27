# Pagination

`ctl list` defaults to `--limit 10`. Users (50), orders (120), and
products (80) all exceed the default. When counting or searching, pass
`--limit 1000` or page explicitly. The CLI does not warn you when results
are truncated.
