# ctl

A deterministic fixture-backed CLI. No network. No live clock. Output for a
given input is fixed.

## Install

```
git clone <repo>
cd CLI_VS_SKILLS
./cli/bin/ctl --help
```

Requires Python 3.9+. Stdlib-only (see `cli/requirements.txt`).

## Synopsis

```
ctl <command> [args...]
```

## Commands

| Command                             | Description                                     |
|-------------------------------------|-------------------------------------------------|
| `ctl list <resource>`               | List records for a resource.                    |
| `ctl get <resource> <id>`           | Fetch a single record.                          |
| `ctl fetch <url-or-slug>`           | Print a fixture markdown page.                  |
| `ctl search --query Q`              | Substring search across resource text fields.   |
| `ctl diff <a> <b>`                  | Structured JSON diff of two records.            |
| `ctl pipeline run <name>`           | Run a named pipeline.                           |
| `ctl pipeline status <name>`        | Show last recorded state for a pipeline.        |
| `ctl cache status`                  | Show cache / state flags.                       |
| `ctl cache clear [<scope>]`         | Clear cached state (scope = pages/search/pipelines/all). |
| `ctl version`                       | Print version.                                  |
| `ctl --help`, `ctl <cmd> --help`    | Usage.                                          |

## Resources

`users` (50), `orders` (120), `tickets` (30), `products` (80), `sessions` (15).

## Common options

| Option                  | Commands      | Description                                  |
|-------------------------|---------------|----------------------------------------------|
| `--status <value>`      | `list`        | Filter rows by exact `status` match.         |
| `--since <date>`        | `list`        | ISO date (`2026-04-20`), ISO datetime, or relative (`7d`, `24h`). |
| `--limit <n>`           | `list`        | Maximum rows. Default: **10**.               |
| `--format json\|yaml\|table` | `list`, `get` | Output format. Default: `table`.        |
| `--query Q`             | `search`      | Required. Substring, or `field:value`.        |
| `--scope <resource>`    | `search`      | Restrict to one resource.                    |
| `--i`                   | `search`      | Case-insensitive. Default: case-sensitive.   |
| `--reindex`             | `search`      | Rebuild the search index.                    |
| `--confirm`             | `pipeline run`| Pass through a confirm gate.                 |
| `--resume`              | `pipeline run`| Resume a partially-applied pipeline.         |
| `--rollback`            | `pipeline run`| Roll back an applied pipeline.               |
| `--verify`              | `pipeline run`| Run an extra verification pass.              |

## Exit codes

| Code | Meaning                                                       |
|-----:|---------------------------------------------------------------|
| `0`  | Success.                                                      |
| `1`  | User error: not found, bad flag, invalid input.               |
| `2`  | Refused: a pipeline needs `--confirm` or a prerequisite.      |

## Environment

| Variable            | Default             | Meaning                                     |
|---------------------|---------------------|---------------------------------------------|
| `CTL_FIXTURES_DIR`  | `<repo>/fixtures`   | Root of the fixture tree.                   |
| `CTL_STATE_DIR`     | `~/.ctl-state/`     | Scratch state for cache / pipeline flags.   |

## Determinism

Pinned "now" is `2026-04-24T00:00:00Z`. Relative `--since` values anchor to
that instant.

## Version

`1.0.0`
