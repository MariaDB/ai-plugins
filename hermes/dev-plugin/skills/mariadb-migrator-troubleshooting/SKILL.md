---
name: mariadb-migrator-troubleshooting
description: "The MySQL-to-MariaDB migrator's known defects and failure playbook — the bash 3.2 traps (unbound SRC_SSL_ARGS, exit 143 without pv, declare -A in staged mode), the SHOW PACKAGE STATUS 1064 that is a mariadb-dump age problem and not a MySQL 8.4 one, the root-user and existing-target-DB refusals, option-file contamination, and what every refusal message from set_config/plan/run/resume means and what to set. Use when a migration was refused, a run failed or timed out, every step reported SKIPPED, or an error message from the migrator tools has to be diagnosed. Read mariadb-migrator first for the tools and preconditions."
---

# Migration — Known Defects and the Failure Playbook

## Known defects to configure around

These are defects in the tooling as released, not in your configuration. Each has
a configuration answer; set it up front rather than discovering it from a failed
run.

| Symptom | Cause | What to set |
| --- | --- | --- |
| `mariadb-dump: Couldn't execute 'SHOW PACKAGE STATUS ...' (1064)` at the dump step | A `mariadb-dump` old enough to issue that MariaDB-only statement against the source. **Not a blanket MySQL 8.4 incompatibility** — current `mariadb-dump` dumps an 8.4 source cleanly (rc=0), and the preflight gates that used to block 8.4 sources were removed as incorrect. Diagnose from the actual error, not from the source version. | Only if the 1064 really appears: `MARIADB_DUMP_BIN` = an upstream `mysqldump` (the one beside the source's own `mysqld`). Do not set this pre-emptively because the source is 8.4 |
| `line 226: SRC_SSL_ARGS[@]: unbound variable` | Expanding an empty array under `set -u` errors on bash before 4.4 (macOS ships 3.2). Hit whenever the SSL args come out empty. | Set `SRC_SSL_MODE` explicitly so the array is never empty, or run on bash 4.4+. Pointing `MARIADB_DUMP_BIN` at upstream `mysqldump` also sidesteps it, but that is a side effect — do not reach for it first |
| The run copied everything correctly but reports `FAILED` with exit **143**, after a 60-second stall | With no `pv`, mode 1 falls back to a heartbeat it kills from an `EXIT` trap; on bash 3.2 the trap's status becomes the script's. | Install `pv` (`brew install pv` / `apt-get install pv`). It is documented as optional, but the fallback is broken |
| `declare: -A: invalid option` in `25_staged_dump.sh` | Mode 3 needs bash 4.0 (`declare -A`) and 4.3 (`wait -n`). `STAGED_PARALLEL=1` does not help. | Nothing — **mode 3 cannot run on bash 3.2.** Install bash 4+, or use mode 1 |
| `SRC/TGT admin and migration users must not be root` | A deliberate safety policy, not a bug. | `ALLOW_ROOT_USERS` = `"1"`, only when migrating as `root` is genuinely intended |
| `ERROR: Target DB already exists` (exit 8) | The target already holds a database of that name — a re-run, or a real collision. | Drop it on the target, or `ALLOW_TARGET_DB_OVERWRITE` = `"1"` if overwriting is intended |
| Mode 2 fails looking for a data-transfer engine | `mariadb-mtk` is not bundled with the tooling. | Install it and put it on `PATH`, or set `SQLINESDATA_BIN` — otherwise use mode 1 |
| A phase script reads back a garbled or empty single value, or the run stops on a `--print-defaults` gate | A `verbose` or `vertical` line in a client option file contaminates every captured query result. | Remove it from `~/.my.cnf` and `/etc/my.cnf.d/*`. The gate is deliberate; do not work around it |
| Access denied for an account whose hash is correct | `caching_sha2_password` without TLS or RSA key exchange, or a hash corrupted in transport. | See the `MIGRATE_APP_USERS` notes in `mariadb-migrator-configure` |

A gate that fires but doesn't change the outcome is **not** part of the
operator's report — see `mariadb-migrator-verify`.

## Failure playbook

| Message | Meaning | Fix |
| --- | --- | --- |
| `... is not a connection configured with mcp.setup` | An account you named is not a configured connection. | `db.list_connections`, then name one of those — or have the connection added with `mcp.setup --addConnection`. |
| `source names SRC_HOST but none of SRC_ADMIN_USER, SRC_USER` | A host with no account to check it by. | Add the account key for that side. |
| `SRC_ADMIN_PASS cannot be set here` | You tried to write a password. | Remove it; set user/host/port and let it resolve. |
| `The MySQL-to-MariaDB migration tooling is not installed` | No install, or the server started before one. | `mcp setup --installMigrator`, then **restart the server**. |
| `Missing required env vars for mode '<mode>': ...` | The configuration is incomplete for that mode. | Add the keys; re-read the mode table in `mariadb-migrator-configure`. |
| `'out' must be relative to the install directory` | An absolute `out`. | Omit `out`, or pass a relative path. |
| `migrator.<command> did not finish within <n>s` | The invocation was stopped at its timeout. | Read the artifacts directory, then `migrator.resume` with that same `out`. |
| Every step `SKIPPED`, exit 0 | A reused `out` directory holding an old `state.json`. | Re-run with `out` omitted. |

When a step actually fails, the run's own `report.json` and `run.log` under
`<install_dir>/<out_dir>` are the real diagnosis — name the step and quote from
its `output_tail` rather than paraphrasing.

## See Also

- `mariadb-migrator` — the overview: tools, preconditions, modes at a glance.
- `mariadb-migrator-configure` — the keys these fixes are set with.
- `mariadb-migrator-modes` — the bash-version limits per mode, and mode 2's data-transfer engine.
- `mariadb-migrator-run` — resuming a stopped run and reading its artifacts.
- `mariadb-migrator-verify` — what belongs in the report and what doesn't.
