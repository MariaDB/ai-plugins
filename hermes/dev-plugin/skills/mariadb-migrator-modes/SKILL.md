---
name: mariadb-migrator-modes
description: "The MySQL-to-MariaDB migration modes and the gate each one brings — one_step (serial streaming), two_step (parallel, needs mariadb-mtk and only retries within a run), staged (dump to disk with a SHA-256 manifest, STAGED_PHASE dump_only/load_only across sessions, needs bash 4), binlog (replication, MySQL 8.0+ and no JSON columns), and why inplace/replace_slave are never picked. Use when choosing or recommending a migration mode, when mariadb-mtk or SQLINESDATA_BIN is missing, when splitting a staged dump and load, or when asked for a low-downtime MySQL-to-MariaDB cutover. Read mariadb-migrator first for the tools and preconditions."
---

# Migration — Choosing the Mode

Pass the mode to `set_config` (as the file's default) **and** to `plan`/`run`;
the per-call one wins, so keep them the same.

The mode ids below are what the tools take. When you talk to the operator, use
the name in the **Called** column instead — the ids are internal and mean nothing
to someone deciding how to migrate.

| # | Mode id | Called | Type | What it does | Pick it when |
| --- | --- | --- | --- | --- | --- |
| 1 | `one_step` | Serial Streaming Copy | offline | `mysqldump` piped straight into the target `mariadb` client, tables sequentially. | **The default choice.** Simplest and most predictable; start here unless something below applies. |
| 2 | `two_step` | Parallel Restartable Streaming Copy | offline | Schema-only dump, then parallel data load via `mariadb-mtk`, then triggers/routines/events. | Large databases *and* `mariadb-mtk` is installed. It is **not** bundled — without it this mode cannot run. Read the resume caveat below before promising restartability. |
| 3 | `staged` | Offline Copy | offline | Per-database compressed dumps to disk with a SHA-256 manifest, then a separate load. Sub-phases `dump_and_load` / `dump_only` / `load_only`. | The dump must land on disk first — a network-restricted or deferred-load migration — or you want checksums. **Needs bash 4** (see `mariadb-migrator-troubleshooting`). |
| 4 | `binlog` | Replication | online | Consistent snapshot with binlog coordinates, then MariaDB replicates from the MySQL binary log. | Low-downtime cutover. Requires a **MySQL 8.0+** source with `binlog_format=ROW`, and the schema must have **no JSON columns** — see below. |
| — | `inplace`, `replace_slave` | — | — | Replace MySQL with MariaDB on the source host itself, over SSH. | **Do not pick these.** They are excluded from the tooling's own menu, need SSH access to the target host, and are documented for advanced scripting only. |

## If mode 2 is picked and `mariadb-mtk` isn't on `PATH`

Mode 2's data-transfer step needs `mariadb-mtk`, and it is not bundled with
the tooling. Before writing the configuration, check two things: whether
`SQLINESDATA_BIN` is already set **in the migrator's own
`config/migration.yaml`** — not the shell environment — since a prior run
may already have written a valid path there; and if not, whether
`mariadb-mtk` resolves on `PATH` via `command -v mariadb-mtk`. Do not assume
it is installed just because mode 2 was chosen.

**Find that config through the tools, never by guessing the install
directory.** `migrator.set_config` returns the config's actual path, and a
run returns `install_dir`. Use one of those — or a prior tool call's
returned path already visible in this conversation — as the single source
of truth. Do not `ls`/`cat` candidate directories you're guessing at (a repo
checkout name, a versioned folder like `-1.4.0-beta`, `~/Mysql-to-MariaDB-Migration`,
etc.): the real install location (commonly under
`~/.local/share/mariadb-migrator/<version>/`, but don't hardcode that either)
is whatever the tools themselves report, and guessing wrong reads as "not
set" when it may already be configured correctly.

**A shell `export SQLINESDATA_BIN=...` does not satisfy this check.** The
`migrator.*` tools run inside the MCP server process, which does not inherit
an operator's later `export` in an unrelated terminal — only the
`SQLINESDATA_BIN` key actually written into `config/migration.yaml` via
`migrator.set_config` counts. If the operator says they've already set it,
confirm it's in the config (or just take the path and write it there
yourself) rather than treating an `export` as sufficient.

**If neither gives you a path, prompt the operator for it.** Don't go
looking for it yourself: no scanning `/usr/local/bin`, `/opt`, home
directories, or a `find` over the filesystem. Beyond being the wrong move
when a straight question is faster, each of those is also its own
approval-gated command, so guessing turns one clear question into several
prompts. Ask something like: *"`mariadb-mtk` isn't on PATH or set as
`SQLINESDATA_BIN` in the migration config — paste the full path, or say the
word to switch to mode 1 instead, which doesn't need it."* Always offer the
mode change as a real alternative in that same prompt, not just the request
for a path.

Once you have a path — from `PATH`, an existing `SQLINESDATA_BIN` in the
config, or the operator — set `SQLINESDATA_BIN` to it via
`migrator.set_config` if it isn't already there. If the operator doesn't
have it installed and doesn't want to, use mode 1.

### What `resume` does and does not resume — mode 2

`migrator.resume` continues the **orchestrator's** step list from `state.json`.
It does not resume the data copy underneath it: `mariadb-mtk` has no
cross-invocation resume. Within a single run it retries transient errors
according to `restart_attempts`, and that is the whole of it.

So resuming an interrupted mode 2 run — killed, host rebooted, connection
dropped — restarts the load step against a target that already holds part of the
data. Whether to drop the partially-loaded objects first is a decision for the
operator, and it needs making explicitly. Read
`<out_dir>/mariadb-mtk/<db>/mariadb-mtk.log` to see which tables actually
finished before advising.

This is the second way a run can look successful and not be: the steps say
`DONE` over a half-loaded table. "Restartable" in the mode's name means
within-run retries, not resumability — do not let it be heard as the latter.

## Mode 3's two phases can be separated by time, and even by session

`STAGED_PHASE` (`dump_and_load` default / `dump_only` / `load_only`) is what
makes mode 3 useful for a network-restricted or deferred-load migration —
but that means `dump_only` and `load_only` are often two separate requests,
possibly days apart, possibly in a conversation with no memory of the
first. Handle that split explicitly:

- **After a `dump_only` run, surface the dump location prominently and
  exactly** — the actual `STAGED_DUMP_DIR` the run used, not a description
  of where it "should" be. This is the one piece of information the
  operator must carry forward to the `load_only` request; burying it in a
  longer report risks it getting lost. State it as its own clearly-labeled
  line, e.g. `Dump directory (needed for load_only): <path>`.
- **Before starting `load_only`, verify the manifest, don't just point
  `STAGED_DUMP_DIR` at it and run.** The dump ships a SHA-256 manifest
  specifically so the dump can be checked before trusting it — confirm the
  files present match the manifest before calling `migrator.run`. A
  mismatch here means a corrupted or partial dump, which is a much clearer
  failure to catch now than partway through a load.
- **`load_only` does not need the source reachable, and the discovery pass
  shouldn't treat it as a problem when it isn't.** The whole point of
  staging is that the dump stands on its own — if `STAGED_PHASE=load_only`
  is what's being configured, don't probe or flag the source connection at
  all; only the target and the dump directory matter for this call.
- **That means a standalone `load_only` request often has no live source
  to build the report's "Source" column from — don't compensate by
  `zcat`/`grep`-parsing the dump SQL for object counts.** Pattern-matching
  `CREATE TABLE`/`VIEW`/`TRIGGER` lines against a mysqldump is unreliable
  (it misses multi-line statements, quoted identifiers, `DELIMITER`-wrapped
  procedures) and needs shell access this step shouldn't require. If a
  `dump_only` baseline was already captured earlier in *this* conversation,
  use that. Otherwise, report only what the target now holds and say
  plainly that no independent source count was available to compare it
  against — that's an honest report, whereas a grep-derived number dressed
  up as a match is not.

### The things that are missing without a target to check them against

`dump_only` never touches a target — the target-verification list in
`mariadb-migrator-verify` (`db.list_schemas`, `db.get_object_details`, row
counts, and so on) doesn't apply to it, because there is nothing to compare
against yet. Verify the dump itself instead: confirm the manifest's checksums
match the files on disk, and report per-database dump file sizes and the
elapsed time — that is the dump-only equivalent of the comparison table, not a
placeholder version of it. Full source-vs-target verification still happens
once, after whichever run actually loads the data (`dump_and_load` or the
later `load_only`).

## The JSON gate on mode 4 is not a configuration item

The source version and `binlog_format` are things you set. The JSON restriction
is not: replication from MySQL to MariaDB fails reliably for any schema carrying
a `JSON` column, under every `binlog_format` value, as soon as there is realistic
write traffic. The tooling blocks it at three independent layers (launcher,
assess, preflight) precisely because it is the requirement operators try to
negotiate.

**Check for it before recommending mode 4, don't wait for the tooling to
refuse it.** Look at the source schema's column types (e.g. via
`db.get_object_details` or a query against `information_schema.columns`) for
any `JSON` column. If mode 4 is on the table — the operator asked for it, or
asked for low-downtime and you were about to suggest it — do this check
first and report the result plainly: *"Found `JSON` columns in
`<schema>.<table>`, so replication (mode 4) isn't an option here — the
offline modes (1, 2, or 3) are what's available."* Don't let the person
discover the gate from a failed preflight when it was checkable in advance.

Do not help anyone route around those gates. If the ask is near-zero downtime on
a JSON-bearing schema, say plainly that this tooling cannot deliver it, and offer
mode 2 inside a maintenance window instead.

## See Also

- `mariadb-migrator` — the overview: tools, preconditions, modes at a glance.
- `mariadb-migrator-configure` — the keys each mode requires.
- `mariadb-migrator-run` — `plan`, `run` and `resume`.
- `mariadb-migrator-verify` — verifying on the target and reporting the result.
- `mariadb-migrator-troubleshooting` — the bash-version defects and the missing data-transfer engine.
