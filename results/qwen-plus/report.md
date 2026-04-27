# CLI_VS_SKILLS report

Total trials judged: **202**

## Scoring mode breakdown

| Mode | Tasks |
|---|---:|
| rule | 40 |
| judge | 41 |
| hybrid | 20 |

## Headline

| Arm | Tasks | Trials | Mean score | 95% CI |
|---|---:|---:|---:|:---|
| `cli-only` | 101 | 101 | 0.314 | [0.249, 0.383] |
| `cli-skills` | 101 | 101 | 0.349 | [0.281, 0.420] |

**Headline delta (cli-skills − cli-only): +0.036**

## Per-bucket scores

| Bucket | Arm | N | Mean | 95% CI |
|---|---|---:|---:|:---|
| ambiguous | `cli-only` | 25 | 0.051 | [0.000, 0.143] |
| ambiguous | `cli-skills` | 25 | 0.116 | [0.029, 0.219] |
| long-horizon | `cli-only` | 20 | 0.269 | [0.185, 0.357] |
| long-horizon | `cli-skills` | 20 | 0.296 | [0.186, 0.414] |
| non-file | `cli-only` | 16 | 0.689 | [0.473, 0.876] |
| non-file | `cli-skills` | 16 | 0.709 | [0.521, 0.869] |
| stateful | `cli-only` | 25 | 0.291 | [0.212, 0.376] |
| stateful | `cli-skills` | 25 | 0.277 | [0.189, 0.369] |
| unplanted-failure | `cli-only` | 15 | 0.449 | [0.272, 0.639] |
| unplanted-failure | `cli-skills` | 15 | 0.547 | [0.341, 0.752] |

## Per-task deltas (sorted by cli-skills − cli-only)

| Task | Title | Bucket | Mode | cli-only | cli-skills | Δ | judge_agreement_min |
|---|---|---|---|---:|---:|---:|---:|
| 092 | Document the top 5 hidden pitfalls of ctl | non-file | judge | 0.000 | 1.000 | +1.000 | 1.0 |
| 049 | My search misses something I can eyeball in the list | ambiguous | judge | 0.000 | 0.714 | +0.714 | 1.0 |
| 029 | Search disagrees with list — figure out why | ambiguous | judge | 0.000 | 0.667 | +0.667 | 1.0 |
| 033 | The email report script is crashing | ambiguous | judge | 0.000 | 0.667 | +0.667 | 1.0 |
| 084 | Deploy to production | unplanted-failure | rule | 0.333 | 1.000 | +0.667 | — |
| 044 | Pipeline refuses to start, no clear reason | ambiguous | judge | 0.000 | 0.571 | +0.571 | 1.0 |
| 096 | Investigative report: are we losing money to dup submits | non-file | judge | 0.000 | 0.571 | +0.571 | 1.0 |
| 058 | Remediate the triple-submit duplicate | long-horizon | hybrid | 0.125 | 0.625 | +0.500 | 1.0 |
| 005 | Find the user with the highest total spend | stateful | rule | 0.143 | 0.571 | +0.429 | — |
| 006 | Identify the product that appears in the most orders | stateful | rule | 0.143 | 0.571 | +0.429 | — |
| 067 | Produce this week's operations report | long-horizon | hybrid | 0.429 | 0.857 | +0.429 | 1.0 |
| 078 | Compare user u017 and one of their orders | unplanted-failure | rule | 0.286 | 0.714 | +0.429 | — |
| 075 | Confirm inventory is reconciled | unplanted-failure | rule | 0.625 | 1.000 | +0.375 | — |
| 062 | Multi-pipeline session with consistent state at the end | long-horizon | hybrid | 0.111 | 0.444 | +0.333 | 1.0 |
| 011 | Follow a link from the troubleshooting page to the incident runbook | stateful | rule | 0.143 | 0.429 | +0.286 | — |
| 052 | Migrate pending orders to paid with checkpoints | long-horizon | hybrid | 0.111 | 0.333 | +0.222 | 1.0 |
| 057 | Verify inventory and remediate each discrepancy | long-horizon | hybrid | 0.333 | 0.556 | +0.222 | 1.0 |
| 097 | Explain to a teammate why their search returned nothing | non-file | judge | 0.000 | 0.143 | +0.143 | 1.0 |
| 000 | Stub: smoke-test the harness | non-file | judge | 1.000 | 1.000 | 0.000 | 1.0 |
| 001 | Fetch the full record for the first user in the list | stateful | rule | 0.500 | 0.500 | 0.000 | — |
| 002 | Identify the user behind the most recently opened ticket | stateful | rule | 0.333 | 0.333 | 0.000 | — |
| 003 | Identify the product sold in the highest-value order | stateful | rule | 0.571 | 0.571 | 0.000 | — |
| 007 | Resolve the user behind the longest active session | stateful | rule | 0.333 | 0.333 | 0.000 | — |
| 008 | Diff the two most recent orders | stateful | rule | 0.429 | 0.429 | 0.000 | — |
| 009 | List orders belonging to the only suspended user | stateful | rule | 0.375 | 0.375 | 0.000 | — |
| 010 | Use search to locate a ticket about billing, then fetch the user | stateful | rule | 0.750 | 0.750 | 0.000 | — |
| 012 | Find the users behind all flagged orders | stateful | rule | 0.000 | 0.000 | 0.000 | — |
| 013 | Investigate the first product that pipe-04 skipped | stateful | rule | 0.143 | 0.143 | 0.000 | — |
| 014 | Check pipeline status and resume if partial | stateful | rule | 0.143 | 0.143 | 0.000 | — |
| 015 | Fetch the user who has placed the most orders | stateful | rule | 0.714 | 0.714 | 0.000 | — |
| 018 | Find the most expensive product and list everyone who bought it | stateful | rule | 0.143 | 0.143 | 0.000 | — |
| 021 | Diff two orders belonging to the same user | stateful | rule | 0.250 | 0.250 | 0.000 | — |
| 022 | Pick the highest-priority open ticket and act on it | stateful | rule | 0.000 | 0.000 | 0.000 | — |
| 023 | Reconcile a product's stock discrepancy | stateful | rule | 0.125 | 0.125 | 0.000 | — |
| 024 | Find a triple-submit duplicate and name which to keep | stateful | rule | 0.125 | 0.125 | 0.000 | — |
| 025 | Run pipe-03 then fetch docs — handle the cache | stateful | rule | 0.000 | 0.000 | 0.000 | — |
| 026 | Investigate Sarah's complaint about billing | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 027 | Diagnose refund burst for user u017 | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 028 | Something weird happened with inventory last week | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 030 | The auth docs page is broken, fix it | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 031 | Customer says they were charged three times | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 032 | Why is the backfill so slow | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 034 | Customer says they never ordered anything but we charged them | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 035 | Which product draws the most complaints | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 036 | A user's session looks hijacked | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 037 | Fix the thing that broke | ambiguous | judge | 0.286 | 0.286 | 0.000 | 1.0 |
| 038 | Find the user named 'chen' without knowing which one | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 039 | Are escalations up this week | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 040 | How many total users do we have | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 041 | User's email doesn't look right in the table | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 042 | Looking up 'u17' returns nothing | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 043 | The diff output is an empty object — figure out why | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 046 | Customer complaint: 'my orders just disappeared' | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 047 | Why does pipe-05 keep failing | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 048 | Should I trust the inventory reconcile result | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 050 | Scan for anything broken right now | ambiguous | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 051 | Recover pipe-07 from partial state and verify | long-horizon | hybrid | 0.111 | 0.111 | 0.000 | 1.0 |
| 053 | Run pipe-04, review skips, remediate what you can | long-horizon | hybrid | 0.000 | 0.000 | 0.000 | 1.0 |
| 055 | Rollback pipe-07 and verify collateral damage is undone | long-horizon | hybrid | 0.125 | 0.125 | 0.000 | 1.0 |
| 059 | Full post-pipeline refresh cycle | long-horizon | hybrid | 0.000 | 0.000 | 0.000 | 1.0 |
| 060 | Backfill missing user emails | long-horizon | hybrid | 0.625 | 0.625 | 0.000 | 1.0 |
| 063 | Prod deploy with pre-flight and verification | long-horizon | hybrid | 0.500 | 0.500 | 0.000 | 1.0 |
| 064 | Full audit of user u017's account | long-horizon | hybrid | 0.556 | 0.556 | 0.000 | 1.0 |
| 065 | Make search fully trustworthy after a pipeline run | long-horizon | hybrid | 0.000 | 0.000 | 0.000 | 1.0 |
| 066 | Process every flagged order through resolution | long-horizon | hybrid | 0.375 | 0.375 | 0.000 | 1.0 |
| 068 | Coordinate rollback across pipe-07 AND pipe-04 | long-horizon | hybrid | 0.125 | 0.125 | 0.000 | 1.0 |
| 071 | Count refunded orders across the dataset | unplanted-failure | rule | 1.000 | 1.000 | 0.000 | — |
| 072 | Fetch /docs/auth and summarize | unplanted-failure | rule | 0.286 | 0.286 | 0.000 | — |
| 073 | Report pipe-07 current state | unplanted-failure | rule | 0.125 | 0.125 | 0.000 | — |
| 074 | Run pipe-05 | unplanted-failure | rule | 0.250 | 0.250 | 0.000 | — |
| 076 | Find the user 'Sarah' via search | unplanted-failure | rule | 0.500 | 0.500 | 0.000 | — |
| 077 | Search for an order after a pipeline run | unplanted-failure | rule | 0.000 | 0.000 | 0.000 | — |
| 079 | Confirm pipe-04 fully succeeded | unplanted-failure | rule | 0.000 | 0.000 | 0.000 | — |
| 080 | Look up order o88 | unplanted-failure | rule | 0.333 | 0.333 | 0.000 | — |
| 081 | Report the first 10 users as a CSV | unplanted-failure | rule | 1.000 | 1.000 | 0.000 | — |
| 082 | Orders from the last 24 hours | unplanted-failure | rule | 1.000 | 1.000 | 0.000 | — |
| 083 | Print everyone's email domain | unplanted-failure | rule | 1.000 | 1.000 | 0.000 | — |
| 085 | Read the runbook after a pipeline run | unplanted-failure | rule | 0.000 | 0.000 | 0.000 | — |
| 087 | Draft a support reply to Sarah | non-file | judge | 1.000 | 1.000 | 0.000 | 1.0 |
| 088 | Why we can't trust pipe-09's OK exit | non-file | judge | 0.714 | 0.714 | 0.000 | 1.0 |
| 089 | Warn new engineers about the --limit default | non-file | judge | 1.000 | 1.000 | 0.000 | 1.0 |
| 090 | Narrative: what this support ticket is actually about | non-file | judge | 1.000 | 1.000 | 0.000 | 1.0 |
| 091 | Summarize the incident runbook in one page | non-file | judge | 1.000 | 1.000 | 0.000 | 1.0 |
| 093 | Explain the u017 refunds to a customer | non-file | judge | 0.857 | 0.857 | 0.000 | 1.0 |
| 094 | Executive brief: inventory integrity today | non-file | judge | 0.571 | 0.571 | 0.000 | 1.0 |
| 098 | Memo: why pipe-04 'succeeded' but didn't actually | non-file | judge | 0.000 | 0.000 | 0.000 | 1.0 |
| 099 | Explain ctl's resource id conventions | non-file | judge | 1.000 | 1.000 | 0.000 | 1.0 |
| 056 | End-to-end: resolve Sarah's situation | long-horizon | hybrid | 0.222 | 0.111 | -0.111 | 1.0 |
| 061 | Full system health check with artifacts | long-horizon | hybrid | 0.556 | 0.444 | -0.111 | 1.0 |
| 095 | Onboarding note: how to run pipe-05 from scratch | non-file | judge | 1.000 | 0.857 | -0.143 | 1.0 |
| 004 | Walk from an escalated ticket to that user's recent orders | stateful | rule | 0.375 | 0.125 | -0.250 | — |
| 019 | Run pipe-05 and report its output | stateful | rule | 0.250 | 0.000 | -0.250 | — |
| 054 | Run the pipe-03 then pipe-05 chain end to end | long-horizon | hybrid | 0.250 | 0.000 | -0.250 | 1.0 |
| 069 | Trace an order end-to-end through the system | long-horizon | hybrid | 0.375 | 0.125 | -0.250 | 1.0 |
| 100 | Readiness memo: is the system healthy enough to ship today | non-file | judge | 0.875 | 0.625 | -0.250 | 1.0 |
| 016 | Chain: escalated ticket → user → their active session | stateful | rule | 0.429 | 0.143 | -0.286 | — |
| 020 | Use search to find a doc, then fetch and summarize it | stateful | rule | 0.286 | 0.000 | -0.286 | — |
| 017 | Find the oldest refunded order and its user | stateful | rule | 0.571 | 0.143 | -0.429 | — |
| 070 | Find every currently-open operational issue | long-horizon | hybrid | 0.444 | 0.000 | -0.444 | 1.0 |
| 045 | Find last week's orders, --since is being weird | ambiguous | judge | 1.000 | 0.000 | -1.000 | 1.0 |
| 086 | Explain what went wrong with pipe-07 and prevention plan | non-file | judge | 1.000 | 0.000 | -1.000 | 1.0 |

## Per-task rule / judge / combined breakdown

| Task | Mode | Arm | rule_score | judge_score | combined |
|---|---|---|---:|---:|---:|
| 092 | judge | `cli-only` | — | 0.000 | 0.000 |
| 092 | judge | `cli-skills` | — | 1.000 | 1.000 |
| 049 | judge | `cli-only` | — | 0.000 | 0.000 |
| 049 | judge | `cli-skills` | — | 0.714 | 0.714 |
| 029 | judge | `cli-only` | — | 0.000 | 0.000 |
| 029 | judge | `cli-skills` | — | 0.667 | 0.667 |
| 033 | judge | `cli-only` | — | 0.000 | 0.000 |
| 033 | judge | `cli-skills` | — | 0.667 | 0.667 |
| 084 | rule | `cli-only` | 0.333 | — | 0.333 |
| 084 | rule | `cli-skills` | 1.000 | — | 1.000 |
| 044 | judge | `cli-only` | — | 0.000 | 0.000 |
| 044 | judge | `cli-skills` | — | 0.571 | 0.571 |
| 096 | judge | `cli-only` | — | 0.000 | 0.000 |
| 096 | judge | `cli-skills` | — | 0.571 | 0.571 |
| 058 | hybrid | `cli-only` | 0.167 | 0.000 | 0.125 |
| 058 | hybrid | `cli-skills` | 0.833 | 0.000 | 0.625 |
| 005 | rule | `cli-only` | 0.143 | — | 0.143 |
| 005 | rule | `cli-skills` | 0.571 | — | 0.571 |
| 006 | rule | `cli-only` | 0.143 | — | 0.143 |
| 006 | rule | `cli-skills` | 0.571 | — | 0.571 |
| 067 | hybrid | `cli-only` | 0.000 | 1.000 | 0.429 |
| 067 | hybrid | `cli-skills` | 0.750 | 1.000 | 0.857 |
| 078 | rule | `cli-only` | 0.286 | — | 0.286 |
| 078 | rule | `cli-skills` | 0.714 | — | 0.714 |
| 075 | rule | `cli-only` | 0.625 | — | 0.625 |
| 075 | rule | `cli-skills` | 1.000 | — | 1.000 |
| 062 | hybrid | `cli-only` | 0.167 | 0.000 | 0.111 |
| 062 | hybrid | `cli-skills` | 0.167 | 1.000 | 0.444 |
| 011 | rule | `cli-only` | 0.143 | — | 0.143 |
| 011 | rule | `cli-skills` | 0.429 | — | 0.429 |
| 052 | hybrid | `cli-only` | 0.167 | 0.000 | 0.111 |
| 052 | hybrid | `cli-skills` | 0.500 | 0.000 | 0.333 |
| 057 | hybrid | `cli-only` | 0.167 | 0.667 | 0.333 |
| 057 | hybrid | `cli-skills` | 0.500 | 0.667 | 0.556 |
| 097 | judge | `cli-only` | — | 0.000 | 0.000 |
| 097 | judge | `cli-skills` | — | 0.143 | 0.143 |
| 000 | judge | `cli-only` | — | 1.000 | 1.000 |
| 000 | judge | `cli-skills` | — | 1.000 | 1.000 |
| 001 | rule | `cli-only` | 0.500 | — | 0.500 |
| 001 | rule | `cli-skills` | 0.500 | — | 0.500 |
| 002 | rule | `cli-only` | 0.333 | — | 0.333 |
| 002 | rule | `cli-skills` | 0.333 | — | 0.333 |
| 003 | rule | `cli-only` | 0.571 | — | 0.571 |
| 003 | rule | `cli-skills` | 0.571 | — | 0.571 |
| 007 | rule | `cli-only` | 0.333 | — | 0.333 |
| 007 | rule | `cli-skills` | 0.333 | — | 0.333 |
| 008 | rule | `cli-only` | 0.429 | — | 0.429 |
| 008 | rule | `cli-skills` | 0.429 | — | 0.429 |
| 009 | rule | `cli-only` | 0.375 | — | 0.375 |
| 009 | rule | `cli-skills` | 0.375 | — | 0.375 |
| 010 | rule | `cli-only` | 0.750 | — | 0.750 |
| 010 | rule | `cli-skills` | 0.750 | — | 0.750 |
| 012 | rule | `cli-only` | 0.000 | — | 0.000 |
| 012 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 013 | rule | `cli-only` | 0.143 | — | 0.143 |
| 013 | rule | `cli-skills` | 0.143 | — | 0.143 |
| 014 | rule | `cli-only` | 0.143 | — | 0.143 |
| 014 | rule | `cli-skills` | 0.143 | — | 0.143 |
| 015 | rule | `cli-only` | 0.714 | — | 0.714 |
| 015 | rule | `cli-skills` | 0.714 | — | 0.714 |
| 018 | rule | `cli-only` | 0.143 | — | 0.143 |
| 018 | rule | `cli-skills` | 0.143 | — | 0.143 |
| 021 | rule | `cli-only` | 0.250 | — | 0.250 |
| 021 | rule | `cli-skills` | 0.250 | — | 0.250 |
| 022 | rule | `cli-only` | 0.000 | — | 0.000 |
| 022 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 023 | rule | `cli-only` | 0.125 | — | 0.125 |
| 023 | rule | `cli-skills` | 0.125 | — | 0.125 |
| 024 | rule | `cli-only` | 0.125 | — | 0.125 |
| 024 | rule | `cli-skills` | 0.125 | — | 0.125 |
| 025 | rule | `cli-only` | 0.000 | — | 0.000 |
| 025 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 026 | judge | `cli-only` | — | 0.000 | 0.000 |
| 026 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 027 | judge | `cli-only` | — | 0.000 | 0.000 |
| 027 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 028 | judge | `cli-only` | — | 0.000 | 0.000 |
| 028 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 030 | judge | `cli-only` | — | 0.000 | 0.000 |
| 030 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 031 | judge | `cli-only` | — | 0.000 | 0.000 |
| 031 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 032 | judge | `cli-only` | — | 0.000 | 0.000 |
| 032 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 034 | judge | `cli-only` | — | 0.000 | 0.000 |
| 034 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 035 | judge | `cli-only` | — | 0.000 | 0.000 |
| 035 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 036 | judge | `cli-only` | — | 0.000 | 0.000 |
| 036 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 037 | judge | `cli-only` | — | 0.286 | 0.286 |
| 037 | judge | `cli-skills` | — | 0.286 | 0.286 |
| 038 | judge | `cli-only` | — | 0.000 | 0.000 |
| 038 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 039 | judge | `cli-only` | — | 0.000 | 0.000 |
| 039 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 040 | judge | `cli-only` | — | 0.000 | 0.000 |
| 040 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 041 | judge | `cli-only` | — | 0.000 | 0.000 |
| 041 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 042 | judge | `cli-only` | — | 0.000 | 0.000 |
| 042 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 043 | judge | `cli-only` | — | 0.000 | 0.000 |
| 043 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 046 | judge | `cli-only` | — | 0.000 | 0.000 |
| 046 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 047 | judge | `cli-only` | — | 0.000 | 0.000 |
| 047 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 048 | judge | `cli-only` | — | 0.000 | 0.000 |
| 048 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 050 | judge | `cli-only` | — | 0.000 | 0.000 |
| 050 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 051 | hybrid | `cli-only` | 0.167 | 0.000 | 0.111 |
| 051 | hybrid | `cli-skills` | 0.167 | 0.000 | 0.111 |
| 053 | hybrid | `cli-only` | 0.000 | 0.000 | 0.000 |
| 053 | hybrid | `cli-skills` | 0.000 | 0.000 | 0.000 |
| 055 | hybrid | `cli-only` | 0.143 | 0.000 | 0.125 |
| 055 | hybrid | `cli-skills` | 0.143 | 0.000 | 0.125 |
| 059 | hybrid | `cli-only` | 0.000 | 0.000 | 0.000 |
| 059 | hybrid | `cli-skills` | 0.000 | 0.000 | 0.000 |
| 060 | hybrid | `cli-only` | 0.500 | 1.000 | 0.625 |
| 060 | hybrid | `cli-skills` | 0.500 | 1.000 | 0.625 |
| 063 | hybrid | `cli-only` | 0.333 | 1.000 | 0.500 |
| 063 | hybrid | `cli-skills` | 0.333 | 1.000 | 0.500 |
| 064 | hybrid | `cli-only` | 0.333 | 1.000 | 0.556 |
| 064 | hybrid | `cli-skills` | 0.333 | 1.000 | 0.556 |
| 065 | hybrid | `cli-only` | 0.000 | 0.000 | 0.000 |
| 065 | hybrid | `cli-skills` | 0.000 | 0.000 | 0.000 |
| 066 | hybrid | `cli-only` | 0.000 | 1.000 | 0.375 |
| 066 | hybrid | `cli-skills` | 0.000 | 1.000 | 0.375 |
| 068 | hybrid | `cli-only` | 0.167 | 0.000 | 0.125 |
| 068 | hybrid | `cli-skills` | 0.167 | 0.000 | 0.125 |
| 071 | rule | `cli-only` | 1.000 | — | 1.000 |
| 071 | rule | `cli-skills` | 1.000 | — | 1.000 |
| 072 | rule | `cli-only` | 0.286 | — | 0.286 |
| 072 | rule | `cli-skills` | 0.286 | — | 0.286 |
| 073 | rule | `cli-only` | 0.125 | — | 0.125 |
| 073 | rule | `cli-skills` | 0.125 | — | 0.125 |
| 074 | rule | `cli-only` | 0.250 | — | 0.250 |
| 074 | rule | `cli-skills` | 0.250 | — | 0.250 |
| 076 | rule | `cli-only` | 0.500 | — | 0.500 |
| 076 | rule | `cli-skills` | 0.500 | — | 0.500 |
| 077 | rule | `cli-only` | 0.000 | — | 0.000 |
| 077 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 079 | rule | `cli-only` | 0.000 | — | 0.000 |
| 079 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 080 | rule | `cli-only` | 0.333 | — | 0.333 |
| 080 | rule | `cli-skills` | 0.333 | — | 0.333 |
| 081 | rule | `cli-only` | 1.000 | — | 1.000 |
| 081 | rule | `cli-skills` | 1.000 | — | 1.000 |
| 082 | rule | `cli-only` | 1.000 | — | 1.000 |
| 082 | rule | `cli-skills` | 1.000 | — | 1.000 |
| 083 | rule | `cli-only` | 1.000 | — | 1.000 |
| 083 | rule | `cli-skills` | 1.000 | — | 1.000 |
| 085 | rule | `cli-only` | 0.000 | — | 0.000 |
| 085 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 087 | judge | `cli-only` | — | 1.000 | 1.000 |
| 087 | judge | `cli-skills` | — | 1.000 | 1.000 |
| 088 | judge | `cli-only` | — | 0.714 | 0.714 |
| 088 | judge | `cli-skills` | — | 0.714 | 0.714 |
| 089 | judge | `cli-only` | — | 1.000 | 1.000 |
| 089 | judge | `cli-skills` | — | 1.000 | 1.000 |
| 090 | judge | `cli-only` | — | 1.000 | 1.000 |
| 090 | judge | `cli-skills` | — | 1.000 | 1.000 |
| 091 | judge | `cli-only` | — | 1.000 | 1.000 |
| 091 | judge | `cli-skills` | — | 1.000 | 1.000 |
| 093 | judge | `cli-only` | — | 0.857 | 0.857 |
| 093 | judge | `cli-skills` | — | 0.857 | 0.857 |
| 094 | judge | `cli-only` | — | 0.571 | 0.571 |
| 094 | judge | `cli-skills` | — | 0.571 | 0.571 |
| 098 | judge | `cli-only` | — | 0.000 | 0.000 |
| 098 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 099 | judge | `cli-only` | — | 1.000 | 1.000 |
| 099 | judge | `cli-skills` | — | 1.000 | 1.000 |
| 056 | hybrid | `cli-only` | 0.333 | 0.000 | 0.222 |
| 056 | hybrid | `cli-skills` | 0.167 | 0.000 | 0.111 |
| 061 | hybrid | `cli-only` | 0.429 | 1.000 | 0.556 |
| 061 | hybrid | `cli-skills` | 0.286 | 1.000 | 0.444 |
| 095 | judge | `cli-only` | — | 1.000 | 1.000 |
| 095 | judge | `cli-skills` | — | 0.857 | 0.857 |
| 004 | rule | `cli-only` | 0.375 | — | 0.375 |
| 004 | rule | `cli-skills` | 0.125 | — | 0.125 |
| 019 | rule | `cli-only` | 0.250 | — | 0.250 |
| 019 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 054 | hybrid | `cli-only` | 0.286 | 0.000 | 0.250 |
| 054 | hybrid | `cli-skills` | 0.000 | 0.000 | 0.000 |
| 069 | hybrid | `cli-only` | 0.167 | 1.000 | 0.375 |
| 069 | hybrid | `cli-skills` | 0.167 | 0.000 | 0.125 |
| 100 | judge | `cli-only` | — | 0.875 | 0.875 |
| 100 | judge | `cli-skills` | — | 0.625 | 0.625 |
| 016 | rule | `cli-only` | 0.429 | — | 0.429 |
| 016 | rule | `cli-skills` | 0.143 | — | 0.143 |
| 020 | rule | `cli-only` | 0.286 | — | 0.286 |
| 020 | rule | `cli-skills` | 0.000 | — | 0.000 |
| 017 | rule | `cli-only` | 0.571 | — | 0.571 |
| 017 | rule | `cli-skills` | 0.143 | — | 0.143 |
| 070 | hybrid | `cli-only` | 0.000 | 1.000 | 0.444 |
| 070 | hybrid | `cli-skills` | 0.000 | 0.000 | 0.000 |
| 045 | judge | `cli-only` | — | 1.000 | 1.000 |
| 045 | judge | `cli-skills` | — | 0.000 | 0.000 |
| 086 | judge | `cli-only` | — | 1.000 | 1.000 |
| 086 | judge | `cli-skills` | — | 0.000 | 0.000 |

## Top 10 tasks where cli-skills beat cli-only

| Task | Title | Δ |
|---|---|---:|
| 092 | Document the top 5 hidden pitfalls of ctl | +1.000 |
| 049 | My search misses something I can eyeball in the list | +0.714 |
| 029 | Search disagrees with list — figure out why | +0.667 |
| 033 | The email report script is crashing | +0.667 |
| 084 | Deploy to production | +0.667 |
| 044 | Pipeline refuses to start, no clear reason | +0.571 |
| 096 | Investigative report: are we losing money to dup submits | +0.571 |
| 058 | Remediate the triple-submit duplicate | +0.500 |
| 005 | Find the user with the highest total spend | +0.429 |
| 006 | Identify the product that appears in the most orders | +0.429 |

## Top 10 tasks where cli-only matched or beat cli-skills

| Task | Title | Δ |
|---|---|---:|
| 045 | Find last week's orders, --since is being weird | -1.000 |
| 086 | Explain what went wrong with pipe-07 and prevention plan | -1.000 |
| 070 | Find every currently-open operational issue | -0.444 |
| 017 | Find the oldest refunded order and its user | -0.429 |
| 016 | Chain: escalated ticket → user → their active session | -0.286 |
| 020 | Use search to find a doc, then fetch and summarize it | -0.286 |
| 004 | Walk from an escalated ticket to that user's recent orders | -0.250 |
| 019 | Run pipe-05 and report its output | -0.250 |
| 054 | Run the pipe-03 then pipe-05 chain end to end | -0.250 |
| 069 | Trace an order end-to-end through the system | -0.250 |

## Low inter-judge agreement (threshold < 0.67)

_no rubric items fell below the threshold_

## Efficiency (secondary signals)

| Arm | Mean tokens | Median tokens | Mean calls | Median calls | Mean wall-s | Median wall-s |
|---|---:|---:|---:|---:|---:|---:|
| `cli-only` | 38967.7 | 4089 | 7.51 | 2 | 27.75 | 8.1 |
| `cli-skills` | 30138.5 | 3952 | 5.72 | 1 | 21.1 | 8.2 |

## Diagnostics

### Rejected commands per arm (agent tried things outside the allowlist)

| Arm | Total rejections |
|---|---:|
| `cli-only` | 44 |
| `cli-skills` | 44 |

