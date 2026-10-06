---
layout: page
title: MCP Tool Reference
subtitle: >-
  Every tool the mariadb-shell MCP server exposes, what it takes, and the
  behaviour that is not obvious from the name.
permalink: /mcp-tools/
description: Reference for the mariadb-shell MCP server tools — db.*, msm.*, sandbox.* and the optional migrator.* group.
---

The server exposes **{{ site.tool_count }} tools in three groups**, plus an optional fourth
that only appears when the migration tooling is installed.

<div class="table-wrap" markdown="1">

| Group | Tools | What they do |
| --- | --- | --- |
| [`db.*`](#db--connections-and-sql) | 8 | List connections and schemas, describe objects, run SQL |
| [`msm.*`](#msm--schema-management) | 12 | Versioned schema projects, releases, deployments |
| [`sandbox.*`](#sandbox--throwaway-servers) | 8 | List deployable server versions; deploy, start, stop and delete local instances |
| [`migrator.*`](#migrator--mysql-to-mariadb) | 4 | MySQL-to-MariaDB migration — **optional, not counted above** |

</div>

<div class="callout" markdown="1">
Arguments below are named as the tools take them. `connection_id` always comes
from a prior `db.connect`. Anything taking a file path is subject to the
allowed-paths list — see [How It Works]({{ '/how-it-works/#paths' | relative_url }}).
</div>

## `db.*` — connections and SQL

<div class="table-wrap" markdown="1">

| Tool | Arguments | Notes |
| --- | --- | --- |
| `db.list_connections` | — | The configured connection URIs. Derived from the shell's secret store, so a sandbox's auto-registered connection appears here too. Call it first. |
| `db.connect` | `uri` | Opens and caches a connection, returns a `connection_id`. The URI is normalized before matching; a URI asking for *more* than was configured (a default schema, an option) is refused. |
| `db.list_schemas` | `connection_id` | Schemas visible to the account. A missing schema is usually privileges. |
| `db.list_objects` | `connection_id`, `schema_name`, `object_type="table"` | `table`, `view`, `procedure`, `function`, `trigger`, `event`. |
| `db.get_object_details` | `connection_id`, `schema_name`, `object_name`, `object_type="table"` | Structured detail — columns, keys, indexes, constraints — not a `CREATE` string. Call this before proposing any schema change. |
| `db.execute_sql` | `connection_id`, `sql`, `params=None` | One statement. Use it when you want rows back or need parameters. |
| `db.execute_sql_script` | `connection_id`, `sql_script=None`, `file_path=None`, `stop_on_error=True`, `limit=None`, `column_metadata=False` | Multi-statement, in order, on the connection's session. **Not a transaction, and a failed statement does not raise** — see the warning below. |
| `db.close` | `connection_id` | Closes it. Idle connections are reaped anyway, but close before deleting a sandbox. |

</div>

<div class="callout callout--warn" markdown="1">
**`db.execute_sql_script` runs the whole script on the connection's session,
but it is not a transaction.** State carries from one statement to the next —
`SET @var`, `USE`, a `START TRANSACTION` / `COMMIT` pair, the MariaDB REST
Service's `USE REST SERVICE` — just as it would typed into a client.

What it does not do is undo itself or raise. A failed statement comes back as an
entry with an `error` key, the script stops there (`stop_on_error=True`), and
everything before it has already taken effect. Check every entry before calling
a script done.

State is lost in one case only: a connection that sat idle long enough to be
closed is reopened before the script runs, and the first entry then carries
`session_restarted: true`. Whatever earlier calls left in the session —
variables, the current schema, an open transaction — is gone.
</div>

## `msm.*` — schema management

MariaDB Schema Management. See
[Tutorial 6]({{ '/tutorials/versioned-schema-with-msm/' | relative_url }}) for the
workflow and the section model.

<div class="table-wrap" markdown="1">

| Tool | Arguments | Notes |
| --- | --- | --- |
| `msm.create_project` | `schema_name`, `target_path`, `copyright_holder`, `license`, `overwrite_existing`, … | Scaffolds `<schema>.msm.project/`. An unrecognized `license` name is rejected — omit it or pass your own text. |
| `msm.get_project_information` | `schema_project_path` | Project metadata. |
| `msm.set_development_version` | `version`, `schema_project_path` | Sets the version in section 910 of the development script. |
| `msm.get_released_versions` | `schema_project_path` | Every released version. |
| `msm.get_last_released_version` | `schema_project_path` | The most recent release. |
| `msm.get_last_deployment_version` | `schema_project_path` | The most recent generated deployment script. |
| `msm.get_deployment_script_versions` | `schema_project_path` | All generated deployment scripts. |
| `msm.get_sql_content_from_section` | `file_path`, `section_id` | Read one section. |
| `msm.set_section_sql_content` | `file_path`, `section_id`, `sql_content` | Write one section. **Always edit sections through these two** so the banners are never corrupted. |
| `msm.prepare_release` | `version`, `next_version`, `schema_project_path`, … | Snapshots the development script and creates an **empty** update script. |
| `msm.generate_deployment_script` | `version`, `schema_project_path`, `overwrite_existing` | Composes the create-or-upgrade artifact. Run **after** filling the update script. |
| `msm.deploy_schema` | `connection_id`, `version`, `schema_project_path`, `backup`, `backup_directory` | Applies a version to a live server. Needs an open `db.connect` connection. |

</div>

<div class="callout callout--warn" markdown="1">
**The ordering rule.** `prepare_release` → **fill the update script (section
240, and 270 for revoked privileges)** → `generate_deployment_script`. Generating before filling
produces a script that creates the schema perfectly on an empty server and
**silently fails to upgrade** an existing install.
</div>

### The section model, in brief

<div class="table-wrap" markdown="1">

| Create script | Update script | Contents |
| --- | --- | --- |
| 130 | 230 | Helper routines, names prefixed `msm_` |
| **140** | **240** | **Non-idempotent: tables, base data — and in an update, all `ALTER`s, backfills and drops of removed objects** |
| **150** | 250 | **Idempotent: views, procedures, functions, triggers, events.** 250 is not deployed — leave it empty |
| 170 | 270 | Authorization — 170: `CREATE ROLE IF NOT EXISTS`, `GRANT`; 270: only `REVOKE`, `DROP ROLE` |
| 180 | — | Optional MariaDB REST Service endpoints (`CREATE OR REPLACE REST …`) |
| 190 | 290 | Removal of the `msm_` helpers |

</div>

Sections **140, 240, 170, 270** become the body of a stored procedure in the
generated script: plain `;`-terminated statements, **no `DELIMITER`**, dynamic SQL
for conditional DDL. Sections **130, 150, 180, 230, 190, 290** are emitted at top
level and use `DELIMITER %%`.

The deployment script runs the target version's **150, 170 and 180 in full on
every deployment**, after the table changes, so new and changed views, routines,
roles, grants and endpoints reach upgraded schemas on their own. The update
script only carries what those can't express: table changes and drops (240), and
`REVOKE` / `DROP ROLE` (270). Never `GRANT` in 270 — on an upgrade it runs before
170 creates a new role, and the deployment fails.

## `sandbox.*` — throwaway servers

See [Tutorial 4]({{ '/tutorials/sandbox-lifecycle/' | relative_url }}).

<div class="table-wrap" markdown="1">

| Tool | Arguments | Notes |
| --- | --- | --- |
| `sandbox.list_available_versions` | `series` | Versions `deploy` can be asked for. No argument: the newest patch of each series. `series="11.8"` or `"11"`: every release below it. Only packages built for this platform are listed, and anything listed can be deployed. |
| `sandbox.deploy` | `port`, `password`, `sandbox_dir`, `allow_root_from`, `server_id`, `ssl=False`, `server_version`, `mariadbd_path`, `mariadbd_options`, `timeout` | Creates and starts an instance, and **registers its connection with the MCP server**. Resolves a server from the `PATH`, then already-downloaded versions, then the published index — **no MariaDB Server need be installed**. `server_version` accepts `11.8.9`, `11.8` or `11`, and is refused together with `mariadbd_path`. |
| `sandbox.start` | `port`, `sandbox_dir`, `mariadbd_path`, `timeout` | Restarts an existing instance with its data intact. |
| `sandbox.stop` | `port`, `sandbox_dir`, `password`, `timeout` | Graceful shutdown. **Needs the root password.** |
| `sandbox.kill` | `port`, `sandbox_dir` | Forceful. The fallback when `stop` will not. |
| `sandbox.delete` | `port`, `sandbox_dir` | Removes the instance. **Refuses a running one** — stop or kill first. |
| `sandbox.vendor` | `port`, `sandbox_dir`, `mariadbd_path` | `MariaDB` or `MySQL`. The sandbox machinery can stand up either. |
| `sandbox.version` | `port`, `sandbox_dir`, `mariadbd_path` | The instance's server version. |

</div>

<div class="callout callout--warn" markdown="1">
**Three failure modes worth memorizing.** A deploy that **hangs** means the
sandbox directory is not on the allowed-paths list. A deploy that succeeds but
whose connection is refused means the **password was blank**. A deploy that fails
on TLS means `ssl: True` without `openssl` — the default of `False` is what you
want.
</div>

<div class="callout callout--warn" markdown="1">
**A downloaded server changes how you stop and restart it.** It is not on the
`PATH`, so `sandbox.start` needs the `mariadbd_path` the deploy reported, and
shutdown needs **`sandbox.kill`** — `sandbox.stop` takes no `mariadbdPath` and
cannot find the binary. The deploy message says so at the time.
</div>

Instances live in `~/.mariadb-shell/sandboxes/<port>/` on macOS and Linux, and
`%USERPROFILE%\MariaDB\mariadb-shell\sandboxes\<port>\` on Windows. Downloaded
servers live separately, one directory per version, under
`~/.local/share/mariadb-sandbox-server/` (`%LOCALAPPDATA%\Programs\mariadb-sandbox-server`
on Windows). Instances create a `root@'%'` account and listen on all interfaces,
so they are a development tool and not something to leave running on an untrusted
network.

## `migrator.*` — MySQL to MariaDB

**Optional and not part of the {{ site.tool_count }}.** These four tools are registered only when
the migration tooling is installed
(`mariadb-shell -- mcp setup --installMigrator`, then restart the server). A
server with no install advertises none of them, rather than four tools whose
every call would fail. Linux and macOS only. See
[Tutorial 9]({{ '/tutorials/mysql-to-mariadb-migration/' | relative_url }}).

<div class="table-wrap" markdown="1">

| Tool | Arguments | Notes |
| --- | --- | --- |
| `migrator.set_config` | `mode`, `env`, `merge=False` | Writes `config/migration.yaml`. Only configured connections may be named; **passwords are refused**. |
| `migrator.plan` | `mode`, `out=None`, `timeout=3600` | Resolves the step list and validates the config. **Executes nothing.** |
| `migrator.run` | `mode`, `out=None`, `timeout=3600` | Performs the migration. **Omit `out`** on a new run. |
| `migrator.resume` | `mode`, `out`, `timeout=3600` | Continues a failed run from its `state.json`. `out` is required here. |

</div>

<div class="callout callout--warn" markdown="1">
**The false success.** The orchestrator is resume-safe. Point `out` at a
directory that already holds a `state.json` and the run reports every step
`SKIPPED`, **exits 0, and migrates nothing**. Omit `out` for every new migration,
pass it only to `resume`, and check that every step says `DONE` — never trust
`succeeded` on its own.
</div>

## Error messages you will meet

<div class="table-wrap" markdown="1">

| Message | Cause | Fix |
| --- | --- | --- |
| *not a configured connection* | The URI is not on the allow-list, or asks for more than was configured (a schema, an option). | `mariadb-shell -- mcp setup`, or drop the extra part from the URI. |
| A call that never returns | A path is not on the allowed-paths list, and the guard fell back to a prompt nothing can answer. | Add the directory with `mcp setup`. |
| *There is no object registered under name 'mcp'* | The shell cannot find its plugins — usually a relocated or broken config home. | Check `~/.mariadb-shell/plugins/`. |
| No `migrator.*` tools at all | The migration tooling is not installed, or the server has not been restarted since it was. | `mcp setup --installMigrator`, then restart. |
| *No module named 'pywintypes'* (Windows) | The Windows shell packages do not yet bundle pywin32. | `pip install pywin32` into the shell's bundled Python. |

</div>
