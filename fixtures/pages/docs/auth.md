# Authentication

ctl does not authenticate. The mock backend trusts the caller entirely.
There is no token store, no API key, no session cookie. Every request is
effectively anonymous. Do not try to log in.

(You are reading this page because someone ran `ctl cache clear` and
repaired the persistent auth-page 404 cache entry. If you get a
404-looking body on this slug instead, that is the stale-cache anomaly;
run `ctl cache clear` and retry.)
