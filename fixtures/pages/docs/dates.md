# Date Filters

`--since` accepts either an ISO-8601 date (`2026-04-20`), a full ISO-8601
datetime (`2026-04-20T12:00:00Z`), or a relative duration (`24h`, `7d`).
Any other input is rejected with `invalid date` and no further hint.
