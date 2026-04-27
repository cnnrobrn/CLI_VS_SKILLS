# Refund Policy

Orders can be refunded within 30 days of `created_at`. Only `paid`
orders are refundable; `pending` orders must be cancelled; `failed`
orders need no action; `refunded` orders are already done. If an order
was refunded by a pipeline (see `refund_source`), investigate the
pipeline state before re-charging -- the refund may have been collateral
damage.
