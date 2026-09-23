---
order: 1
slug: notes-app-sandbox
title: "Build a Notes App schema and deploy it on a sandbox"
description: >-
  The complete round trip. The agent designs a MariaDB schema for a note-taking
  app using the bundled skills, deploys a throwaway MariaDB server, runs the
  schema on it, and reads the objects back to prove it worked.
level: beginner
duration: "20 min"
area: getting-started
tools: ["sandbox.deploy", "db.connect", "db.execute_sql_script", "db.list_objects"]
skills: ["mariadb-schema-create-script", "mariadb-create-table"]
path_label: "First Steps, Step 1 · Schema Lifecycle, Step 1"
prerequisites:
  - "A plugin installed in your harness — see [Get Started](../../get-started/)."
  - "`mariadb-shell -- mcp setup` run once, with the directory you will work in on the allowed-paths list."
  - "Nothing else — the sandbox brings its own MariaDB Server if the machine has none."
---

This is the tutorial everything else builds on. By the end you will have a
`notes_app.sql` script on disk, a running MariaDB server on port 3310 with that
schema in it, and a clear picture of which part of the work came from the
**skills** and which from the **MCP tools**.

Nothing here touches a database you care about. The sandbox is a throwaway
server that lives in one folder, and the last step deletes it.

## Ask for the schema

Open your agent in an empty directory — one that is on the MCP server's
allowed-paths list — and start with the schema itself. No database is involved
yet; this step produces a file:

<div class="prompt" markdown="1">
*Create a MariaDB database schema named `notes_app` for a note-taking app and
store it in a `notes_app.sql` file.*
</div>

Before it writes a single `CREATE`, the agent reads the
`mariadb-schema-create-script` skill, and from there the `mariadb-create-table`
and `mariadb-create-index` skills. That is what makes the output *MariaDB* SQL
rather than generic SQL.

Three tells that the skills were actually used:

**The script opens and closes with a settings block.** Every script the skill
produces saves the session's checks and SQL mode, switches to `utf8mb4`, and
restores everything at the end:

```sql
-- Save current session settings and disable checks for faster, safer bulk import
SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO,STRICT_TRANS_TABLES';
SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0;

SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT, @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS;
SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION;
SET NAMES utf8mb4;
```

**Primary keys are native `UUID`, not `CHAR(36)`.** MariaDB has had a real
`UUID` column type since 10.7, and `UUID_v7()` generates time-ordered values, so
you get the index locality of an auto-increment without exposing a row count to
the outside world:

```sql
-- A person who writes notes.
CREATE OR REPLACE TABLE `notes_app`.`user` (
  `id`           UUID NOT NULL DEFAULT UUID_v7(),
  `email`        VARCHAR(255) NOT NULL,
  `display_name` VARCHAR(120) NOT NULL,
  `created_at`   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_email` (`email`)
) ENGINE=InnoDB;
```

**`CREATE SCHEMA IF NOT EXISTS`, and `CREATE OR REPLACE TABLE`.** The skill
prefers `SCHEMA` over `DATABASE`, and MariaDB's atomic `CREATE OR REPLACE` over
a `DROP`-then-`CREATE` pair — so re-running the script is safe and never leaves
you with the table gone and the create failed.

A reasonable Notes App comes out as five tables — `user`, `notebook`, `note`,
`tag` and the `note_tag` junction — plus a view or two. The exact shape will vary;
what should not vary is the MariaDB-specific detail above.

<div class="callout callout--tip" markdown="1">
**Push back and watch it use the skills again.** Ask *"make `note.body` full-text
searchable"* or *"add row history to `note` so I can see what it looked like last
week"*. The second one should produce a **system-versioned table**
(`WITH SYSTEM VERSIONING`) — a MariaDB feature with no MySQL equivalent, and one
the agent only reaches for because a skill told it about it.
</div>

## Deploy the sandbox

Now the MCP tools take over, and a real server appears:

<div class="prompt" markdown="1">
*Spin up a MariaDB sandbox instance on port 3310.*
</div>

That is everything you type. What the agent runs in response is the call below —
shown so you can recognise it going past:

```text
sandbox.deploy(port=3310, password="…", ssl=False)
```

A port is all you have to give. You do not need to invent a root password — the
agent sets one and hands it to the MCP server with the connection, so nothing
downstream ever asks you for it.

Three things happen that are worth knowing about:

- A real `mariadbd` starts, with its data directory under
  `~/.mariadb-shell/sandboxes/3310/`. No container runtime is involved. The
  server itself comes from your `PATH` if one there fits; otherwise the tool
  downloads a version, verifies its checksum and unpacks it — so this works on a
  machine with no MariaDB Server at all. The deploy's message says which of the
  two happened.
- The connection `root@127.0.0.1:3310` is **registered with the MCP server
  automatically**, password and all. You do not have to re-run `mcp setup` to
  let the agent connect to it.
- TLS is off (`ssl: False`), which is why a command-line client may need
  `--skip-ssl` later. Turning it on requires `openssl` on the machine.

### When you do want to choose the password

Name one in the prompt whenever you intend to reach the server from outside the
agent — a command-line client, a GUI, an application you are pointing at it:

<div class="prompt" markdown="1">
*Spin up a MariaDB sandbox instance on port 3310 with root password `demo-pw`.*
</div>

The same call the agent made before, now carrying the password you chose:

```text
sandbox.deploy(port=3310, password="demo-pw", ssl=False)
```

The rest of this tutorial works either way; the later steps go through the agent,
which already has the credentials.

<div class="callout callout--warn" markdown="1">
**Do not ask for a blank password.** It is the one value that is accepted and
then breaks everything: the connection gets registered, nothing can open it, and
the failure reads like a permissions problem rather than a password problem.
Either say nothing and let the agent choose, or give it a real one.
</div>

If the deploy *hangs* rather than failing, the sandbox directory is not on the
allowed-paths list — the path guard is waiting for a confirmation a headless
agent cannot give. Run `mariadb-shell -- mcp setup` and add it.

## Connect and run the script

With the sandbox up, point the agent at the file you made in step 1:

<div class="prompt" markdown="1">
*Connect to that sandbox and run `notes_app.sql` against it.*
</div>

Two calls this time by the agent — one to open the connection, one to run
the file down it:

```text
db.connect(uri="root@127.0.0.1:3310")
db.execute_sql_script(file_path="/abs/path/notes_app.sql", connection_id="…")
```

Two behaviours here explain most of the surprises people hit later:

- **The script file has to be somewhere the MCP server was given access to.**
  If your working directory was never allowed, the agent simply sends the same
  SQL inline instead — which works just as well, and is why you will sometimes
  see it paste a script rather than point at one.
- **Each statement in a script runs on its own fresh session.** Invisible for an
  ordinary create script; fatal for anything that sets something in one
  statement and reads it in the next. When that is what you need, say so and ask
  for the statements to be run one at a time on a single connection. The MariaDB
  REST Service grammar is the usual case — that is
  [Tutorial 8](../rest-endpoints/).

## Read the result back

The last step is the one that turns "the agent said it worked" into "it worked",
and it is worth asking for explicitly. The difference is between the agent
summarizing what it just did and the agent going back to the server to look:

<div class="prompt" markdown="1">
*Don't tell me what you ran — go and read it back off the server. Which schemas
exist, which tables are in `notes_app`, and what are `note`'s columns?*
</div>

You should see `notes_app` in the schema list, your five tables in the object
list, and `note`'s columns — including the `UUID` primary key and the foreign
key to `user` — in the details.

<div class="prompt" markdown="1">
*Now insert three sample users and five notes, then show me each user with their
note count.*
</div>

That last query is a good sanity check on the foreign keys. It is also a
question rather than a script, which is a distinction worth knowing about —
[Tutorial 2](../run-sql-and-scripts/) covers when it matters.

## Clean up

The sandbox is a real server process. Stop it and delete it when you are done:

<div class="prompt" markdown="1">
*Stop and delete the sandbox on port 3310.*
</div>

Which the agent carries out as two calls, in this order:

```text
sandbox.stop(port=3310, password="…")
sandbox.delete(port=3310)
```

A sandbox cannot be deleted while it is running, so the stop has to land first.
If a stop fails — a wedged server, a forgotten password — the agent forces it
down and then deletes it. Asking for both in one sentence, as above, means you
never have to think about the order.

<h2 class="no-step" id="one-prompt">The whole thing in one prompt</h2>

You have now seen each step on its own. In practice you would not type five
prompts — you would type one, because agents do this *better* as a single
instruction than as five: the later steps constrain the earlier ones, so an
agent that knows it will have to run the script on a real server writes a more
careful script.

This is the same tutorial as one prompt, and it is the shape to use once you
trust what it does:

<div class="prompt" markdown="1">
*Work in the current directory and complete every step in order.*

*1. Create a MariaDB database schema named `notes_app` for a note-taking app and
store it in a `notes_app.sql` file.*

*2. Spin up a sandbox instance on port 3310, connect to it and run
`notes_app.sql` against it.*

*3. Don't tell me what you ran — read it back off the server. List the tables you
created and show me the columns of the `note` table.*

*4. Then stop and delete the sandbox, even if an earlier step failed.*
</div>

Step 4 is the habit worth forming early: ask for the teardown in the same breath
as the creation, so a run that times out halfway does not leave a server
listening and a directory behind.

<h2 class="no-step" id="what-you-built">What you built</h2>

A `notes_app.sql` script whose MariaDB-specific decisions came from the skills,
run against a real server that the agent created, verified and then removed —
without you ever typing a connection string or a password into a config file.

The two halves you just used are the whole product. Everything else on this site
is a deeper version of one of them.

**Where to go next**

- [Run SQL and SQL scripts](../run-sql-and-scripts/) — a statement versus a whole
  file, and why the difference keeps biting people.
- [Explore an existing database](../browse-schema-objects/) — the same tools
  pointed at a schema you did *not* write.
- [Version the schema with MSM](../versioned-schema-with-msm/) — turn this
  one-off script into something you can ship version 2 of.
