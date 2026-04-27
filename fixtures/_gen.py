"""Generate the full fixture tree under /fixtures.

Deterministic:  seeded with random.Random(42).
Idempotent:     re-running produces identical output.
No network:     everything is synthesised locally.
Pinned 'now':   2026-04-24T00:00:00Z.

Run from anywhere:
    python3 /Users/<you>/.../CLI_VS_SKILLS/fixtures/_gen.py

or from the repo root:
    python3 fixtures/_gen.py
"""
from __future__ import annotations

import json
import os
import random
from datetime import datetime, timedelta, timezone

SEED = 42
NOW = datetime(2026, 4, 24, 0, 0, 0, tzinfo=timezone.utc)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = HERE  # fixtures/_gen.py lives in fixtures/


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rand_ts(rng: random.Random, max_days_back: int = 30) -> datetime:
    """Random timestamp in the `max_days_back` days before NOW."""
    seconds = rng.randint(0, max_days_back * 24 * 60 * 60)
    return NOW - timedelta(seconds=seconds)


def _write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

USER_STATUSES = ["active", "pending", "suspended"]
USER_ROLES = ["admin", "member", "viewer"]
USER_ORGS = [f"org-{i}" for i in range(1, 6)]

FIRST_NAMES = [
    "Alex", "Blair", "Casey", "Dana", "Eden", "Frankie", "Gale", "Harper",
    "Indra", "Jules", "Kai", "Lee", "Morgan", "Nico", "Ola", "Pat",
    "Quinn", "Rowan", "Sky", "Toby", "Uma", "Val", "Wren", "Xan",
    "Yael", "Zion",
]
LAST_NAMES = [
    "Adler", "Brooks", "Chen", "Diaz", "Evans", "Flores", "Gomez", "Hayes",
    "Ito", "Jensen", "Khan", "Lopez", "Mori", "Nair", "Ortiz", "Park",
    "Quiroz", "Rao", "Singh", "Tan", "Unger", "Vega", "Wong", "Xu",
    "Yoon", "Zima",
]
EMAIL_DOMAINS = ["acme.io", "globex.com", "initech.co", "umbrella.org", "wayne.inc"]


def gen_users(rng: random.Random) -> list[dict]:
    users = []
    for i in range(1, 51):
        uid = f"u{i:03d}"
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        local = f"{first.lower()}.{last.lower()}"
        domain = rng.choice(EMAIL_DOMAINS)
        users.append({
            "id": uid,
            "email": f"{local}@{domain}",
            "name": f"{first} {last}",
            "status": rng.choice(USER_STATUSES),
            "role": rng.choice(USER_ROLES),
            "org_id": rng.choice(USER_ORGS),
            "created_at": _iso(_rand_ts(rng)),
        })

    # Anomaly A15 — Sarah Chen as u042: suspended 2026-04-22, billing-broken.
    u042 = next(u for u in users if u["id"] == "u042")
    u042.update({
        "email": "sarah.chen@acme.io",
        "name": "Sarah Chen",
        "status": "suspended",
        "role": "member",
        "org_id": "org-2",
        "created_at": "2025-11-03T09:14:22Z",
        "status_changed_at": "2026-04-22T11:47:00Z",
        "notes": "billing dispute; account flipped to suspended pending review",
    })

    # Anomaly A18 — NULL emails on u023, u031, u049.
    for uid in ("u023", "u031", "u049"):
        u = next(u for u in users if u["id"] == uid)
        u["email"] = None

    return users


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

ORDER_STATUSES = ["paid", "pending", "refunded", "failed"]
CURRENCIES = ["USD", "EUR", "GBP"]


def gen_orders(rng: random.Random, user_ids: list[str], product_ids: list[str]) -> list[dict]:
    orders = []
    for i in range(1, 121):
        oid = f"o{i:03d}"
        n_products = rng.randint(1, 4)
        products = rng.sample(product_ids, k=n_products)
        orders.append({
            "id": oid,
            "user_id": rng.choice(user_ids),
            "total_cents": rng.randint(199, 199_900),
            "currency": rng.choice(CURRENCIES),
            "status": rng.choice(ORDER_STATUSES),
            "product_ids": products,
            "created_at": _iso(_rand_ts(rng, max_days_back=45)),
        })

    # ---- Anomaly A14 — triple-submit bug on o067/o068/o069. -----------------
    # Same user, same total_cents, three timestamps within 3 seconds on
    # 2026-04-10T08:12:xxZ. By convention, the lowest id keeps `paid`;
    # the other two are refunded.
    base_ts = datetime(2026, 4, 10, 8, 12, 15, tzinfo=timezone.utc)
    dup_user = "u008"
    dup_total = 4999
    dup_products = ["p007", "p012"]
    for idx, oid in enumerate(("o067", "o068", "o069")):
        o = next(o for o in orders if o["id"] == oid)
        o["user_id"] = dup_user
        o["total_cents"] = dup_total
        o["currency"] = "USD"
        o["product_ids"] = dup_products
        o["created_at"] = _iso(base_ts + timedelta(seconds=idx))
        o["status"] = "paid" if idx == 0 else "refunded"
        if idx > 0:
            o["refunded_at"] = _iso(base_ts + timedelta(seconds=idx, minutes=7))
            o["refund_reason"] = "duplicate submission (triple-submit)"

    # ---- Anomaly A10 — pipe-07 collateral refunds on o088/o091. -------------
    # Belong to u017; refunded within 60 minutes on 2026-04-18.
    o088 = next(o for o in orders if o["id"] == "o088")
    o091 = next(o for o in orders if o["id"] == "o091")
    o088.update({
        "user_id": "u017",
        "total_cents": 12999,
        "currency": "USD",
        "status": "refunded",
        "created_at": "2026-04-18T14:29:50Z",
        "refunded_at": "2026-04-18T14:48:12Z",
        "refund_reason": "collateral: pipe-07 partial apply",
        "refund_source": "pipe-07",
    })
    o091.update({
        "user_id": "u017",
        "total_cents": 3499,
        "currency": "USD",
        "status": "refunded",
        "created_at": "2026-04-18T14:30:05Z",
        "refunded_at": "2026-04-18T15:21:03Z",
        "refund_reason": "collateral: pipe-07 partial apply",
        "refund_source": "pipe-07",
    })

    # Give u017 a few additional orders so "pull all of u017's orders" is a
    # real paging question (14 orders total is the ground truth cited in the
    # task README). We grab the first N non-conflicting order ids and reassign
    # them to u017.
    u017_extras = [
        "o004", "o019", "o032", "o045", "o058", "o073",
        "o082", "o099", "o104", "o112", "o118", "o120",
    ]
    for oid in u017_extras:
        o = next(o for o in orders if o["id"] == oid)
        o["user_id"] = "u017"
    # (o088, o091 already u017; total = 14.)

    # ---- Anomaly A15 — Sarah Chen (u042) flagged orders. --------------------
    for oid, when in (
        ("o102", "2026-04-19T08:12:00Z"),
        ("o107", "2026-04-20T14:30:00Z"),
        ("o115", "2026-04-21T18:51:44Z"),
    ):
        o = next(o for o in orders if o["id"] == oid)
        o["user_id"] = "u042"
        o["status"] = "paid"
        o["flagged"] = True
        o["flag_reason"] = "billing anomaly; see ticket t019"
        o["created_at"] = when

    return orders


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------

TICKET_STATUSES = ["open", "resolved", "escalated"]
TICKET_PRIORITIES = ["low", "med", "high", "critical"]
TICKET_SUBJECTS = [
    "Cannot log in after password reset",
    "Invoice PDF has wrong totals",
    "Export CSV is missing the last column",
    "Need to transfer ownership of org-3 workspace",
    "Two-factor code never arrives by SMS",
    "Refund not processed after 10 business days",
    "Webhook retries are looping forever",
    "Dashboard graphs show zero for all metrics",
    "Bulk delete hangs on large product catalogs",
    "API key rotation broke our production deploy",
    "Feature request: scheduled exports",
    "Acme integration keeps disconnecting",
    "Session ended mid-checkout, cart was lost",
    "Admin console shows stale user roles",
    "Sub-user cannot see orders they created",
    "Stripe reconciliation is off by one penny",
    "Seats count mismatch after plan downgrade",
    "Email notifications are going to spam",
    "billing broken since the weekend",  # <- slot for t019 (Sarah)
    "SSO redirect loops on Safari only",
    "Permissions changed without any audit entry",
    "Export queue appears stuck since Tuesday",
    "Password reset emails never arrive for @gmail",
    "API rate limit headers missing from responses",
    "Upload fails silently for files over 5 MB",
    "Runbook incident-42 links to a 404 page",
    "New member invite shows as already-accepted",
    "Billing address cannot be updated from UI",
    "Product SKU conflict when duplicating a catalog",
    "Real-time sync falls behind during high load",
]


def gen_tickets(rng: random.Random, user_ids: list[str]) -> list[dict]:
    tickets = []
    for i in range(1, 31):
        tid = f"t{i:03d}"
        subject = TICKET_SUBJECTS[i - 1]
        tickets.append({
            "id": tid,
            "user_id": rng.choice(user_ids),
            "subject": subject,
            "body": f"Customer reports: {subject.lower()}.",
            "status": rng.choice(TICKET_STATUSES),
            "priority": rng.choice(TICKET_PRIORITIES),
            "created_at": _iso(_rand_ts(rng)),
        })

    # Anomaly A15 — Sarah Chen's escalated ticket t019.
    t019 = next(t for t in tickets if t["id"] == "t019")
    t019.update({
        "user_id": "u042",
        "subject": "billing broken since the weekend",
        "body": (
            "I can't check out since Saturday. Three of my recent orders are "
            "flagged and my account just got suspended this morning with no "
            "warning. Please look at o102, o107, o115. This is urgent."
        ),
        "status": "escalated",
        "priority": "critical",
        "created_at": "2026-04-22T12:03:41Z",
    })

    return tickets


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

PRODUCT_CATEGORIES = ["widgets", "gadgets", "consumables", "services", "subscriptions"]
PRODUCT_NAMES = [
    "Acme Foghorn", "Acme Anvil", "Acme Rocket Skates", "Acme Earthquake Pills",
    "Globex Ionizer", "Globex Plasma Cell", "Globex Heat Sink",
    "Initech TPS Binder", "Initech Red Stapler", "Initech Cover Sheet",
    "Umbrella Vaccine", "Umbrella Tracker", "Umbrella Field Kit",
    "Wayne Grapple", "Wayne Cowl", "Wayne Batmobile Wax",
    "Standard Widget A", "Standard Widget B", "Standard Widget C",
    "Premium Gadget X", "Premium Gadget Y", "Premium Gadget Z",
    "Consumable Ink", "Consumable Toner", "Consumable Ribbon",
    "Service Install", "Service Tuneup", "Service Audit",
    "Monthly Plan", "Annual Plan",
]


def gen_products(rng: random.Random) -> list[dict]:
    products = []
    for i in range(1, 81):
        pid = f"p{i:03d}"
        name = PRODUCT_NAMES[(i - 1) % len(PRODUCT_NAMES)]
        if i > len(PRODUCT_NAMES):
            name = f"{name} Mk {i // len(PRODUCT_NAMES)}"
        products.append({
            "id": pid,
            "name": name,
            "sku": f"SKU-{i:04d}",
            "price_cents": rng.choice([199, 499, 999, 1999, 4999, 9999, 19999]),
            "inventory": rng.randint(0, 500),
            "category": rng.choice(PRODUCT_CATEGORIES),
            "active": rng.random() > 0.15,
        })

    # Anomaly A11 — pipe-09 inventory mismatches on p014, p037, p061.
    # The recorded inventory differs from the reconciled "true" inventory by a
    # known amount. The reconcile pipeline only surfaces the delta when run
    # with --verify.
    mismatches = {
        "p014": ("recorded 120, warehouse reports 117", -3),
        "p037": ("recorded 42, warehouse reports 50", +8),
        "p061": ("recorded 0, warehouse reports 5 (phantom out-of-stock)", +5),
    }
    for pid, (note, delta) in mismatches.items():
        p = next(p for p in products if p["id"] == pid)
        p["inventory_discrepancy"] = {
            "note": note,
            "delta": delta,
            "source": "pipe-09 reconcile",
        }

    # Anomaly A17 — pipe-04 skipped two products (p044, p077). Annotate them.
    p044 = next(p for p in products if p["id"] == "p044")
    p077 = next(p for p in products if p["id"] == "p077")
    p044["pipe_04_skip_reason"] = "missing SKU prefix (legacy import)"
    p077["pipe_04_skip_reason"] = "price_cents null in source feed"

    return products


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 14) Chrome/124.0.0.0 Mobile",
    "curl/8.4.0",
]


def gen_sessions(rng: random.Random, user_ids: list[str]) -> list[dict]:
    sessions = []
    for i in range(1, 16):
        sid = f"s{i:02d}"
        started = _rand_ts(rng)
        ended = started + timedelta(minutes=rng.randint(3, 240))
        sessions.append({
            "id": sid,
            "user_id": rng.choice(user_ids),
            "started_at": _iso(started),
            "ended_at": _iso(ended),
            "ip": f"10.0.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
            "user_agent": rng.choice(USER_AGENTS),
        })
    return sessions


# ---------------------------------------------------------------------------
# Pipelines
# ---------------------------------------------------------------------------

def pipelines() -> list[dict]:
    """Return the 10 pipeline fixture definitions.

    Each fixture carries:
      - metadata          (name, id, description)
      - definition        (canonical list of steps)
      - default_run_result   what a vanilla `ctl pipeline run` prints
      - partial_failure_state (pipe-07 only) — recovery state
      - resume_result / rollback_result (pipe-07 only)
      - verify_result (pipe-09 only)
      - requires_confirm, requires_prereq, marks_stale_after_run (meta)
    """
    return [
        # --------------------------- pipe-01 ---------------------------------
        {
            "id": "pipe-01",
            "name": "deploy-prod",
            "description": "Deploy current build to production.",
            "definition": {
                "steps": [
                    "build",
                    "test",
                    "push-image",
                    "rollout",
                ],
            },
            "requires_confirm": True,
            "refused_message": "refused",
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/4] build: ok",
                    "[2/4] test: ok",
                    "[3/4] push-image: ok",
                    "[4/4] rollout: ok",
                    "pipeline deploy-prod: ok",
                ],
            },
        },

        # --------------------------- pipe-02 ---------------------------------
        {
            "id": "pipe-02",
            "name": "seed-staging",
            "description": "Seed staging database from fixtures.",
            "definition": {"steps": ["truncate", "load-fixtures", "vacuum"]},
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/3] truncate: ok",
                    "[2/3] load-fixtures: 275 rows",
                    "[3/3] vacuum: ok",
                    "pipeline seed-staging: ok",
                ],
            },
        },

        # --------------------------- pipe-03 ---------------------------------
        {
            "id": "pipe-03",
            "name": "rotate-keys",
            "description": "Rotate API signing keys.",
            "definition": {"steps": ["generate-keypair", "publish-jwks"]},
            "marks_cache_stale_after_run": True,  # anomaly A4
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/2] generate-keypair: ok",
                    "[2/2] publish-jwks: ok",
                    "pipeline rotate-keys: ok",
                ],
            },
        },

        # --------------------------- pipe-04 ---------------------------------
        {
            "id": "pipe-04",
            "name": "backfill-products",
            "description": "Backfill product catalog from legacy feed.",
            "definition": {"steps": ["fetch-feed", "validate", "upsert"]},
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/3] fetch-feed: 82 rows",
                    "[2/3] validate: 80 ok, 2 skipped",
                    "[3/3] upsert: 80 rows",
                    "pipeline backfill-products: ok (2 skipped)",
                ],
                "stderr_lines": [
                    "Warning: 2 records skipped (see /tmp/pipe-04.skipped)",
                ],
                "side_effects": {
                    "write_file": {
                        "path": "/tmp/pipe-04.skipped",
                        "content": "p044\np077\n",
                    },
                },
            },
        },

        # --------------------------- pipe-05 ---------------------------------
        {
            "id": "pipe-05",
            "name": "reindex-search",
            "description": "Rebuild search indexes from scratch.",
            "definition": {"steps": ["snapshot-source", "rebuild-index", "swap-alias"]},
            "requires_prereq": "pipe-03",  # anomaly A3
            "prereq_failure_message": "prerequisite not met",
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/3] snapshot-source: ok",
                    "[2/3] rebuild-index: ok",
                    "[3/3] swap-alias: ok",
                    "pipeline reindex-search: ok",
                ],
            },
        },

        # --------------------------- pipe-06 ---------------------------------
        {
            "id": "pipe-06",
            "name": "purge-audit-logs",
            "description": "Delete audit logs older than retention window.",
            "definition": {"steps": ["scan", "delete"]},
            "requires_confirm": True,
            "refused_message": "refused",
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/2] scan: 412193 rows eligible",
                    "[2/2] delete: ok",
                    "pipeline purge-audit-logs: ok",
                ],
            },
        },

        # --------------------------- pipe-07 ---------------------------------
        {
            "id": "pipe-07",
            "name": "backfill-orders",
            "description": "Backfill historical orders from cold storage.",
            "definition": {
                "steps": ["load-batch", "apply", "verify"],
                "total_records": 200,
            },
            "partial_failure_state": {
                "completed": 147,
                "remaining": 53,
                "state": "partial",
                "failed_at": "2026-04-18T14:42:09Z",
                "cause": "apply step timed out at record 148 (downstream RDS freeze)",
                "collateral_refunds": ["o088", "o091"],
            },
            "default_run_result": {
                # Anomaly A10: exits 0 (!) despite partial apply.
                "status": "ok",
                "exit_code": 0,
                "lines": [
                    "[1/3] load-batch: 200 records queued",
                    "[2/3] apply: 147/200 applied",
                    "[3/3] verify: partial",
                    "pipeline backfill-orders: ok",
                ],
                "stderr_lines": [
                    "Warning: partial apply -- see 'ctl pipeline status pipe-07' for details",
                ],
                "marks_search_index_stale": True,  # anomaly A6
                "already_applied_error": "already partially applied",
            },
            "resume_result": {
                "status": "ok",
                "lines": [
                    "[1/3] load-batch: resuming from record 148",
                    "[2/3] apply: 53/53 applied",
                    "[3/3] verify: ok",
                    "pipeline backfill-orders: ok (resumed, 200/200)",
                ],
            },
            "rollback_result": {
                "status": "ok",
                "lines": [
                    "[1/2] revert-apply: 147 records rolled back",
                    "[2/2] verify: ok",
                    "pipeline backfill-orders: rolled back",
                ],
            },
        },

        # --------------------------- pipe-08 ---------------------------------
        {
            "id": "pipe-08",
            "name": "sync-inventory",
            "description": "Sync product inventory from the warehouse feed.",
            "definition": {"steps": ["fetch-feed", "upsert"]},
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/2] fetch-feed: 80 rows",
                    "[2/2] upsert: 80 rows",
                    "pipeline sync-inventory: ok",
                ],
            },
        },

        # --------------------------- pipe-09 ---------------------------------
        {
            "id": "pipe-09",
            "name": "reconcile-inventory",
            "description": "Reconcile recorded inventory against warehouse truth.",
            "definition": {"steps": ["scan-recorded", "scan-warehouse", "compare"]},
            "default_run_result": {
                # Anomaly A11 — exits 0 with 'ok' but is untrustworthy.
                "status": "ok",
                "lines": [
                    "[1/3] scan-recorded: 80 rows",
                    "[2/3] scan-warehouse: 80 rows",
                    "[3/3] compare: ok",
                    "pipeline reconcile-inventory: ok",
                ],
            },
            "verify_result": {
                "status": "ok",
                "verified": True,
                "discrepancies": 3,
                "lines": [
                    "[1/4] scan-recorded: 80 rows",
                    "[2/4] scan-warehouse: 80 rows",
                    "[3/4] compare: 3 discrepancies found",
                    "[4/4] emit-report: ok",
                    "pipeline reconcile-inventory: ok, verified: true, discrepancies: 3",
                ],
                "details": [
                    {"product_id": "p014", "recorded": 120, "warehouse": 117, "delta": -3},
                    {"product_id": "p037", "recorded": 42, "warehouse": 50, "delta": 8},
                    {"product_id": "p061", "recorded": 0, "warehouse": 5, "delta": 5},
                ],
            },
        },

        # --------------------------- pipe-10 ---------------------------------
        {
            "id": "pipe-10",
            "name": "vacuum-sessions",
            "description": "Vacuum expired sessions.",
            "definition": {"steps": ["scan", "delete"]},
            "default_run_result": {
                "status": "ok",
                "lines": [
                    "[1/2] scan: 9 rows eligible",
                    "[2/2] delete: 9 rows",
                    "pipeline vacuum-sessions: ok",
                ],
            },
        },
    ]


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

# Real page content. Kept short; the agent reads these like docs pages.
PAGES: list[tuple[str, str, str]] = [
    ("/docs/getting-started", "Getting Started", """\
Welcome to the ctl reference environment. Every command is backed by a
committed fixture -- there is no live backend. Output is deterministic;
treat it as ground truth for tests.

Start with `ctl --help`, then try `ctl list <resource>` for one of the
five resources: users, orders, tickets, products, sessions.
"""),
    ("/docs/auth", "Authentication", """\
ctl does not authenticate. The mock backend trusts the caller entirely.
There is no token store, no API key, no session cookie. Every request is
effectively anonymous. Do not try to log in.

(You are reading this page because someone ran `ctl cache clear` and
repaired the persistent auth-page 404 cache entry. If you get a
404-looking body on this slug instead, that is the stale-cache anomaly;
run `ctl cache clear` and retry.)
"""),
    ("/docs/pagination", "Pagination", """\
`ctl list` defaults to `--limit 10`. Users (50), orders (120), and
products (80) all exceed the default. When counting or searching, pass
`--limit 1000` or page explicitly. The CLI does not warn you when results
are truncated.
"""),
    ("/docs/formatting", "Output Formatting", """\
`--format` is one of `json`, `yaml`, `table`. Default is `table`, which
truncates long fields with an ellipsis and does not warn you. For any
machine processing, use `--format json`.
"""),
    ("/docs/search", "Search", """\
`ctl search --query Q` is case-sensitive. Pass `--i` for insensitive
matching. After certain pipelines run the index can go stale; pass
`--reindex` to rebuild.
"""),
    ("/docs/dates", "Date Filters", """\
`--since` accepts either an ISO-8601 date (`2026-04-20`), a full ISO-8601
datetime (`2026-04-20T12:00:00Z`), or a relative duration (`24h`, `7d`).
Any other input is rejected with `invalid date` and no further hint.
"""),
    ("/docs/troubleshooting", "Troubleshooting", """\
- `not found`: wrong id, or wrong resource for the id (e.g. `ctl get users o001`).
- `refused`: a pipeline wants `--confirm`. Check the corresponding runbook.
- `prerequisite not met`: another pipeline must have run first in this session.
- `invalid date`: see /docs/dates for accepted shapes.
- Stale data after pipelines: run `ctl cache clear` and
  `ctl search --reindex`.

Related reading:
- /runbook/incident-42 -- the canonical writeup of the pipe-07 partial.
- /runbook/deploy
- /runbook/backfill
"""),
    ("/docs/exit-codes", "Exit Codes", """\
0  success
1  user error (bad flag, not found, invalid input, unknown resource)
2  refused / prerequisite-unmet

Any other code is a bug.
"""),
    ("/docs/fixtures", "Fixtures", """\
Fixtures live under `fixtures/` (or `$CTL_FIXTURES_DIR` if set). Changing
them changes every command's output. Do not edit fixtures during a
benchmark run. State lives in `~/.ctl-state/` (or `$CTL_STATE_DIR`) and
is safe to `rm -rf` between runs.
"""),
    ("/help/billing", "Billing FAQ", """\
Billing questions should be filed with priority `high`. Use `critical`
only when revenue is actively stuck (e.g. check-out hard-fails for a
paying account). Refund eligibility: see /help/refunds.
"""),
    ("/help/refunds", "Refund Policy", """\
Orders can be refunded within 30 days of `created_at`. Only `paid`
orders are refundable; `pending` orders must be cancelled; `failed`
orders need no action; `refunded` orders are already done. If an order
was refunded by a pipeline (see `refund_source`), investigate the
pipeline state before re-charging -- the refund may have been collateral
damage.
"""),
    ("/help/export", "Exporting Data", """\
`ctl list <resource> --limit 1000 --format json > out.json` is the
canonical export. YAML works but is slower to parse downstream.
"""),
    ("/help/duplicates", "Duplicate Orders Convention", """\
When a user accidentally triple-submits a checkout (same user_id, same
total_cents, timestamps within a few seconds), keep the order with the
lowest id as `paid` and refund the others with
`refund_reason = "duplicate submission (triple-submit)"`.

This is a convention, not an automatic check; it has to be done by hand
or by a targeted pipeline.
"""),
    ("/help/organizations", "Organizations", """\
Users belong to one of org-1 through org-5. `ctl` does not support
cross-org queries directly; combine multiple single-org listings
yourself.
"""),
    ("/runbook/incident-42", "Runbook: Incident 42 -- pipe-07 Partial Apply (2026-04-18)", """\
On 2026-04-18 at 14:42:09Z the `backfill-orders` pipeline (`pipe-07`)
timed out during its `apply` step. The run printed `pipeline
backfill-orders: ok` and exited 0. It was not ok.

Ground truth:
- 147 of 200 records were applied before the downstream RDS freeze.
- 53 records remain unprocessed.
- Two orders (o088 and o091, both belonging to user u017) were flipped
  to `status=refunded` as collateral damage, within 60 minutes of each
  other (refunded_at timestamps on 2026-04-18 between 14:48 and 15:22).

Detection:
    ctl pipeline status pipe-07
    -> completed: 147/200, remaining: 53, state: partial

Recovery options:
- Finish the remaining work:
    ctl pipeline run pipe-07 --resume
- Roll back the 147 applied records:
    ctl pipeline run pipe-07 --rollback
- Running `ctl pipeline run pipe-07` a second time without a flag is an
  error (`already partially applied`). It will not silently re-apply.

Side effects:
- The search index is marked stale when pipe-07 runs. Run
  `ctl search --reindex` after finishing pipe-07 before trusting
  `ctl search --scope orders` results.
- Affected users should be notified; u017 in particular was refunded
  twice by this incident and may open a ticket.
"""),
    ("/runbook/incident-77", "Runbook: Incident 77", """\
An earlier search reindex failure. If `ctl pipeline run reindex-search`
still fails, escalate; a CLI-side retry won't help.
"""),
    ("/runbook/deploy", "Runbook: Deploy", """\
`ctl pipeline run deploy-prod` requires `--confirm`. Without the flag the
pipeline prints `refused` to stderr and exits 2. This is by design.
"""),
    ("/runbook/rotate-keys", "Runbook: Rotate Keys", """\
Rotating keys invalidates every active API token. Coordinate with
integrators. The pipeline also marks the page cache stale -- run
`ctl cache clear` afterwards or `ctl fetch /docs/*` will start returning
the canned 404 page.
""" ),
    ("/runbook/backfill", "Runbook: Backfill", """\
The `backfill-orders` pipeline (pipe-07) is NOT safe to blind-re-run
after a partial apply. See /runbook/incident-42. Choose explicitly
between `--resume` and `--rollback`.
"""),
    ("/runbook/reconcile", "Runbook: Reconcile Inventory", """\
`ctl pipeline run reconcile-inventory` exits 0 with `status: ok` by
default. That output is untrustworthy -- it does not actually verify
anything unless you pass `--verify`, which emits the discrepancy list
and an accurate summary. Always pass `--verify` for audits.
"""),
    ("/policy/retention", "Data Retention", """\
Audit logs retained 90 days. Sessions 30 days after `ended_at`. Orders
and users indefinitely. Resolved tickets 2 years after resolution.
"""),
    ("/policy/security", "Security Policy", """\
Do not paste real customer data into issues. All fixture data in this
repo is synthetic. Suspected leaks should be reported to security@ --
synthetic too.
"""),
    ("/about/changelog", "Changelog", """\
1.0.0 - 2026-04-24 - initial benchmark release.
"""),
    ("/about/faq", "FAQ", """\
Q: Why does `ctl list users` only show 10 rows?
A: Default limit is 10. Pass `--limit 100` or higher.

Q: Why does `ctl search --query acme` find nothing?
A: Search is case-sensitive by default. Try `--query Acme` or pass `--i`.

Q: Why does `ctl diff u001 o001` return `{}`?
A: Cross-resource diffs silently produce an empty object. Compare ids
   from the same resource.

Q: What does the `refused` exit mean?
A: The pipeline wants `--confirm`. See the relevant runbook.
"""),
    ("/about/team", "About the Team", """\
The platform team owns `ctl`. File issues in the tracker; do not DM
individual engineers.
"""),
    ("/blog/2026-04-01-skills", "Why we publish SKILLS.md", """\
`--help` answers 'what flags exist'. SKILLS.md answers 'what should I do
next'. Only the second one shortens a debug loop.
"""),
]


def _md_page(title: str, body: str) -> str:
    return f"# {title}\n\n{body.rstrip()}\n"


# The special 404 body returned when the cache is stale. Kept in its own
# slot (not under pages/) so it is not reachable by a direct `ctl fetch`.
PAGE_CACHE_STALE_404 = """\
# 404 Not Found

This page is unavailable because the local page cache is stale. This is
a known failure mode after certain pipelines run. Clear the cache with
`ctl cache clear` and try again.
"""

# Permanent 404 for /docs/auth even without staleness (Anomaly A7). We
# still route it through the same 404 body so the resolution advice (cache
# clear) applies.
PAGE_DOCS_AUTH_MARKER = "__docs_auth_always_stale__"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def main() -> None:
    rng = random.Random(SEED)

    # Products first -- orders refer to product_ids.
    products = gen_products(rng)
    product_ids = [p["id"] for p in products]

    users = gen_users(rng)
    user_ids = [u["id"] for u in users]

    orders = gen_orders(rng, user_ids, product_ids)
    tickets = gen_tickets(rng, user_ids)
    sessions = gen_sessions(rng, user_ids)

    def emit_resource(name: str, rows: list[dict]) -> None:
        base = os.path.join(FIXTURES, "api", name)
        _write_json(os.path.join(base, "list.json"), rows)
        for r in rows:
            _write_json(os.path.join(base, f"{r['id']}.json"), r)

    emit_resource("users", users)
    emit_resource("orders", orders)
    emit_resource("tickets", tickets)
    emit_resource("products", products)
    emit_resource("sessions", sessions)

    for pipe in pipelines():
        _write_json(os.path.join(FIXTURES, "pipelines", f"{pipe['name']}.json"), pipe)

    # Pages. We write /docs/auth as a marker file so the CLI knows to return
    # the 404 body; every other page writes its real markdown content.
    for slug, title, body in PAGES:
        rel = slug.lstrip("/") + ".md"
        _write_text(os.path.join(FIXTURES, "pages", rel), _md_page(title, body))

    # Anomaly A7 — /docs/auth 404 marker. We intentionally do NOT write a
    # real page here; the CLI interprets missing pages/docs/auth.md combined
    # with an allowlist as 'canned 404 from stale cache'.
    # We also keep the 'stale cache 404' body here for the CLI to read.
    _write_text(
        os.path.join(FIXTURES, "pages", "_stale_404.md"),
        PAGE_CACHE_STALE_404,
    )

    print(
        f"wrote {len(users)} users, {len(orders)} orders, {len(tickets)} tickets, "
        f"{len(products)} products, {len(sessions)} sessions, "
        f"{len(pipelines())} pipelines, {len(PAGES)} pages"
    )


if __name__ == "__main__":
    main()
