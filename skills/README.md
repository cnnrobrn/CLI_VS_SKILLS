# Skills directory

This directory holds the skill library for the `cli + skills` arm of
the benchmark. It replaces the older monolithic `SKILLS.md`.

This README is for human contributors. The agent under test never
reads it. The agent sees only an auto-generated index of names and
descriptions, and loads individual skill bodies on demand.

## Architecture

- **One file per skill.** Each `*.md` (except this README) defines
  exactly one skill.
- **Frontmatter is the index.** Every skill file begins with YAML
  frontmatter containing `name` and `description`. The harness
  parses the frontmatter at runtime to build the index that goes into
  the agent's system prompt.
- **Body is loaded on demand.** When the agent decides a skill looks
  relevant (based on the description), it calls a `load_skill` tool
  with the name. The harness returns the markdown body.
- **Forces selection.** The agent does not get the whole library
  dumped into context. It has to read the descriptions, decide which
  skills apply, and pull them. Well-named, well-described skills
  win.

## Skill file format

```markdown
---
name: paginate-list-results
description: Use when running `ctl list <resource>` to count records or filter to "all" of something. The default `--limit` is 10 and silently truncates with no warning, so any cardinality answer derived from the default page is almost certainly wrong.
---

# Pagination

One short paragraph naming the problem.

## Wrong invocation

What a naive agent does.

## Right invocation

The documented fix, with the exact `ctl` command.

## Common mistakes

Bullet list of pitfalls.
```

### Frontmatter rules

- `name`: lowercase, hyphenated; must match the filename without
  `.md`.
- `description`: ONE sentence, ≤ 250 characters, leading with the
  trigger condition ("Use when ..."). The agent reads only this in
  the index, so write it for skill *selection*, not as a body
  summary.

### Body rules

- Lead with the problem in one paragraph.
- Show the wrong invocation, then the right one.
- Include exact `ctl` commands and any relevant resource ids
  (`o088`, `u042`, `t019`, ...).
- For recipe skills, list steps in order.
- ~30-80 lines is the sweet spot. Trim padding.

## Adding a new skill

1. Create `skills/<name>.md` with the frontmatter and body sections
   above.
2. Make sure `name` in frontmatter matches the filename.
3. If the new skill maps to a planted anomaly in
   `fixtures/ANOMALIES.md`, add an entry to the table below.
4. The harness picks up the new skill on next run -- no registry to
   update.

## Skill catalog

| name                              | description                                                                                                | covers anomaly       |
|-----------------------------------|------------------------------------------------------------------------------------------------------------|----------------------|
| paginate-list-results             | Override the default `--limit 10` when counting or listing all records.                                    | A1                   |
| confirm-destructive-pipeline      | `pipe-01` and `pipe-06` refuse without `--confirm`; CLI gives no hint.                                     | A2                   |
| pipeline-prerequisites            | `pipe-05` requires `pipe-03` to have run; error is unhelpfully terse.                                      | A3                   |
| clear-cache-after-pipe03          | Running `pipe-03` marks `/docs/*` cache stale; clear with `ctl cache clear`.                               | A4                   |
| case-insensitive-search           | `ctl search` is case-sensitive by default; pass `--i` or match actual case.                                | A5                   |
| reindex-stale-search              | `ctl list` and `ctl search` disagree after `pipe-07`; `ctl search --reindex` resyncs.                      | A6                   |
| clear-stale-page-cache            | `/docs/auth` returns a default-state 404; clear with `ctl cache clear`.                                    | A7                   |
| diff-resource-type-validation     | `ctl diff a b` returns `{}` for cross-type ids -- not "identical."                                         | A8                   |
| since-flag-formats                | `--since` accepts ISO date, ISO datetime+Z, or `Nd`/`Nh`. Nothing else.                                    | A9                   |
| recover-pipe07-partial            | `pipe-07` is pre-baked partial; choose `--resume` or `--rollback`.                                         | A10                  |
| verify-reconcile-inventory        | `pipe-09` lies about its result without `--verify`.                                                        | A11                  |
| lookup-resource-by-id             | `ctl get` is exact-match only; search by name first.                                                       | A12                  |
| format-output-fidelity            | `--format table` truncates fields > 23 chars; use `--format json`.                                         | A13                  |
| resolve-triple-submit-duplicates  | Three orders same user/total/seconds-apart: keep lowest id, refund the rest.                               | A14                  |
| handle-suspended-account          | Sarah Chen (u042); flagged orders o102/o107/o115; ticket t019.                                             | A15                  |
| discover-runbooks                 | The CLI does not link to runbooks; `/runbook/incident-42` etc. live in pages.                              | A16                  |
| read-pipe04-skip-file             | `pipe-04` writes skipped ids to `/tmp/pipe-04.skipped` (p044, p077).                                       | A17                  |
| handle-null-emails                | Three users have null email; filter before `.lower()`.                                                     | A18                  |
| diagnose-refund-burst             | Recipe: end-to-end u017 / pipe-07 collateral diagnosis.                                                    | A1, A10, A16         |
| verify-migration-cleanup          | Recipe: pre/post count idiom anchored on pipe-09.                                                          | A1, A11, A13         |
| find-flagged-records              | Recipe: search-then-filter chain anchored on Sarah Chen.                                                   | A1, A5, A15          |
| cross-check-list-and-search       | Recipe: detect index drift by comparing two queries that should agree.                                     | A1, A6               |
| output-format-conventions         | Idiom: prefer JSON; never trust table for free text.                                                       | A13                  |
| resource-id-conventions           | Idiom: `u`/`o`/`t`/`p`/`s` prefixes; key identities cheat-sheet.                                           | A8, A12              |

24 skills total. Every planted anomaly (A1-A18) is covered by at
least one skill.
