# Duplicate Orders Convention

When a user accidentally triple-submits a checkout (same user_id, same
total_cents, timestamps within a few seconds), keep the order with the
lowest id as `paid` and refund the others with
`refund_reason = "duplicate submission (triple-submit)"`.

This is a convention, not an automatic check; it has to be done by hand
or by a targeted pipeline.
