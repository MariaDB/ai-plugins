---
order: 9
slug: mysql-to-mariadb-migration
title: "Migrate a MySQL database to MariaDB"
description: >-
  Drive the MySQL-to-MariaDB Migrator from the agent — choose a mode, ask for it
  in a prompt that carries everything the agent needs, plan it, run it, and
  verify the result. Rehearsed on two throwaway servers before it touches
  anything real.
level: advanced
duration: "60 min"
area: migration
tools: ["migrator.set_config", "migrator.plan", "migrator.run", "migrator.resume", "sandbox.deploy"]
skills: ["mariadb-migrator", "mariadb-migrator-modes", "mariadb-migrator-configure", "mariadb-migrator-run", "mariadb-migrator-verify", "mysql-to-mariadb"]
path_label: "Build an API, Step 2"
prerequisites:
  - "**Linux or macOS.** The migration tooling is a POSIX shell program and is not available on Windows."
  - "The tooling installed: `mariadb-shell -- mcp setup --installMigrator`, then **restart the MCP server** — the tools only register on the next start."
  - "`mariadb` and `mariadb-dump` on the server's `PATH`. `pv` should be there too."
  - "**A local MySQL Server installation**, if you want to follow the rehearsal below. MariaDB sandboxes are downloaded on demand; MySQL ones are not."
  - "Both the source and the target as **configured MCP connections**."
---

The MySQL-to-MariaDB Migrator is a standalone program — a Python orchestrator
driving a directory of shell scripts — that copies databases from a MySQL source
to a MariaDB target. The four `migrator.*` tools configure it and drive it.

You do not drive it yourself: you ask the agent, and it writes the migrator's
configuration and calls the tools. So **getting your prompt right is most of the
work**. A configuration the agent cannot write correctly is refused outright,
which is good; a plausible-but-incomplete one fails deep inside the dump step,
which is not — and the difference is usually something your prompt left out.

<div class="callout callout--warn" markdown="1">
**If the agent says it has no `migrator.*` tools, the tooling is not installed.**
The server advertises none of them at all rather than four tools whose every call
would fail. Install with `mariadb-shell -- mcp setup --installMigrator` and
**restart the server** — the change takes effect on the next start, not the
current one.
</div>

## Rehearse on two sandboxes first

Never learn a migration tool on the database you need. The sandbox machinery can
stand up a **MySQL** instance as well as a MariaDB one, so the whole rehearsal
fits on one laptop:

<div class="prompt" markdown="1">
*Deploy a MySQL sandbox on port 3307 and a MariaDB sandbox on port 3308. Put a
small but realistic schema in the MySQL one — a few tables with foreign keys, a
view, a stored procedure and a trigger — and seed it with data. Then confirm both
show up in `db.list_connections`.*
</div>

<div class="callout callout--tip" markdown="1">
**MariaDB sandboxes arrive on demand; MySQL ones do not.** If the MariaDB
package for the version you ask for is not on the machine already, it is
downloaded and set up for you. A MySQL sandbox is built from a local MySQL
Server installation, so that one has to be there first.
</div>

If you lose track of which port got which server, ask. The agent checks the
servers rather than assuming, with a call like this:

```text
sandbox.vendor(port=3307)   → "MySQL"
sandbox.vendor(port=3308)   → "MariaDB"
```

Both sandboxes are registered as MCP connections when they are deployed, which
matters for the next step.

## Choose a mode

If your prompt does not name a mode, the agent picks the **Serial Streaming
Copy** — the simplest and most predictable of the four. Name one explicitly when
something below applies, and use the name rather than the id: the ids are
internal, and the name is what the agent will use when it talks back to you.

| Ask for | Mode id | Type | What it does | Pick it when |
| --- | --- | --- | --- | --- |
| **Serial Streaming Copy** | `one_step` | offline | `mysqldump` piped straight into the target client, tables sequentially. | **The default choice.** Start here unless something below applies. |
| **Parallel Restartable Streaming Copy** | `two_step` | offline | Schema-only dump, then parallel data load via `mariadb-mtk`, then triggers, routines and events. | Large databases *and* `mariadb-mtk` installed — it is **not** bundled. |
| **Offline Copy** | `staged` | offline | Per-database compressed dumps to disk with a SHA-256 manifest, then a separate load. | The dump must land on disk first, or you want checksums. **Needs bash 4.** |
| **Replication** | `binlog` | online | Consistent snapshot with binlog coordinates, then MariaDB replicates from the MySQL binary log. | Low-downtime cutover. Needs **MySQL 8.0+**, `binlog_format=ROW`, and **no JSON columns**. |

You do not have to check those requirements yourself — ask, and let the agent
tell you what is actually available:

<div class="prompt" markdown="1">
*I need the shortest possible downtime on this migration. Which mode can I
actually use here — check the source version and whether the schema has any JSON
columns before you answer.*
</div>

## What your prompt has to tell the agent

The agent writes the migrator's configuration with `migrator.set_config`, and
that call is **refused** rather than allowed to fail later if it names a server
that is not a configured connection or tries to set a password. Both refusals
are there to stop an agent inventing infrastructure or leaking a secret — and
both are things your prompt can steer.

Three things to supply. Only the third is unusual.

**Name both servers, with their ports.** The agent can only use servers that are
already configured connections, so name them the way `db.list_connections` lists
them. Sandboxes are registered when they are deployed, so in this rehearsal they
are already there.

<div class="callout callout--warn" markdown="1">
**Always give the port, on both sides.** The port is half of the URI the
password is looked up under. Leave it out and it reads as 3306 — so on any other
port the lookup silently finds nothing and the run fails much later, somewhere
that does not mention ports. Be consistent about the host, too: if the
connection is `root@127.0.0.1:3307`, do not write `root@localhost:3307`.
</div>

**Name the databases schema to migrate.** One, or a list. If you are asking for an
Offline Copy and intend to dump now and load somewhere else later, say that —
it is a different request from a straight-through migration, and the dump
location is the one thing you will need to carry forward.

**Never put a password in your prompt.** The agent cannot set one — every
password key is refused if given a value — and it does not need one. Each
password is read from the shell's secret store at the moment the migration runs.
If you paste a credential in, you have leaked it into the transcript for nothing.

Put together, a prompt that carries everything:

<div class="prompt" markdown="1">
*Migrate the `shop` and `billing` databases from `root@127.0.0.1:3307` to
`root@127.0.0.1:3308` with a Serial Streaming Copy. Plan it first and show me
the steps before you run anything.*
</div>

## Plan before you run

Always plan first. `plan` resolves the step list and validates the
configuration — it **executes nothing** and does not need a reachable server,
which makes it free to run as often as you like.

<div class="prompt" markdown="1">
*Plan a migration of `shop` and `billing` from `root@127.0.0.1:3307` to
`root@127.0.0.1:3308`, and walk me through what each step will do to the source
and to the target, before we run anything.*
</div>

Read the step list — it is the contract for what `run` will do. The call the
agent makes to produce it:

```text
migrator.plan(mode="one_step")   → the resolved step list, nothing executed
```

## Run it

Once the plan looks right, run it.

<div class="prompt" markdown="1">
*Go ahead and run it.*
</div>

This is the one that actually moves data. The agent invokes it; you watch what
comes back:

```text
migrator.run(mode="one_step")   → a report, one entry per step
```

<div class="callout callout--warn" markdown="1">
**Never accept "migration completed successfully" on its own.** A run can report
success and move nothing — most often because it reused an earlier run's working
directory, in which case every step is skipped and the run still exits cleanly.
The agent's summary will not necessarily say so. Ask for the detail:

*Show me the status of every step in that run, and the row counts now on the
target — don't just tell me it succeeded.*

Every step should say `DONE`. A run of skipped steps is a "success" that did
nothing.
</div>

## Resume a failed run

If a run stops partway — a timeout, a dropped connection, a failed step — it can
be picked up where it left off rather than started again.

<div class="prompt" markdown="1">
*That run stopped partway. Resume it from where it got to.*
</div>

Steps already marked `DONE` are skipped and the run picks up at the first one
that is not. Resuming needs the stopped run's artifacts directory, so ask in the
same session, while the agent still has it — otherwise tell it which run
directory to use. The agent fills that directory in from the stopped run and
calls:

```text
migrator.resume(mode="one_step", out="artifacts/migrate_one_step_…")
```

## Verify on the target

The migrator writes its own report when a run finishes. Treat it as a claim, not
a result: the check that counts is a query against the target, and this is where
the agent earns its keep, because it can check everything rather than the few
schema objects you would have thought to check.

<div class="prompt" markdown="1">
*Connect to the target and verify the migration: every table from the source
exists with the same row count, every view, routine and trigger came across, the
foreign keys are all there, and no table lost its primary key. Show me a table of
source vs. target counts and flag any row that does not match.*
</div>

Things worth checking explicitly, because they are what actually differs:

- **Row counts per table**, source against target. `COUNT(*)`, not `TABLE_ROWS`.
- **Views, stored routines, triggers and events** — these travel separately from
  data in several modes, and are the usual casualty.
- **Character sets and collations.** MySQL's `utf8mb4_0900_ai_ci` does not exist
  in MariaDB; the closest equivalent is `utf8mb4_uca1400_ai_ci`. The
  `mysql-to-mariadb` skill covers the substitutions.
- **`JSON` columns.** MySQL's `JSON` is a native binary type; MariaDB's is a
  `LONGTEXT` alias with a check constraint. Data survives, but anything relying
  on MySQL's internal ordering does not — and Replication mode refuses JSON
  columns entirely.
- **Accounts and grants**, if you asked for the application's users to come
  across as well.

## Then read the application side

The data being across is half the job. The `mysql-to-mariadb` skill is the other
half — what changes for the *application*: connector differences, SQL mode
defaults, functions that behave differently, and the features MariaDB has that
you can now use.

<div class="prompt" markdown="1">
*Now review this application's SQL and connector code against MariaDB. What will
break, what will behave differently, and what could be simplified using something
MariaDB has that MySQL does not?*
</div>

<h2 class="no-step" id="what-you-built">What you learned</h2>

- The tools only exist once the tooling is installed **and the server is
  restarted**. Linux and macOS only.
- Rehearse on two sandboxes — a MySQL source and a MariaDB target — before the
  migration touches anything real.
- The agent writes the configuration, but only from what you gave it: **name both
  servers with their ports, name the databases, and never paste a password.**
- Ask for a mode by name. Say nothing and you get a Serial Streaming Copy.
- Planning is free and executes nothing — ask for a plan first, every time.
- **"Succeeded" is not verification.** Ask for every step's status, then verify on
  the target with queries rather than reading the report.

**Where to go next**

- [Version the migrated schema with MSM](../versioned-schema-with-msm/) — put the
  schema you just inherited under version control before you change it.
- [Diagnose a slow query](../diagnose-a-slow-query/) — plans differ after a
  migration; this is when you find out.
