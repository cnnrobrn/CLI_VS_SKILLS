# Runbook: Rotate Keys

Rotating keys invalidates every active API token. Coordinate with
integrators. The pipeline also marks the page cache stale -- run
`ctl cache clear` afterwards or `ctl fetch /docs/*` will start returning
the canned 404 page.
