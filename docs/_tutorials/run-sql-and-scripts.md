---
order: 2
slug: run-sql-and-scripts
title: "Run SQL and SQL scripts"
description: >-
  Ask the agent to run a statement, run a whole file, and read results back.
  Covers the one behaviour that causes most surprises — a script is not a
  transaction, so a failure halfway leaves the first half in place.
level: beginner
duration: "15 min"
area: sql
tools: ["db.list_connections", "db.connect", "db.execute_sql", "db.execute_sql_script", "db.close"]
skills: ["mariadb-select", "mariadb-insert", "mariadb-transactions"]
path_label: "First Steps, Step 2"
prerequisites:
  - "[Tutorial 1](../notes-app-sandbox/), or any configured MariaDB connection."
  - "A sandbox on port 3310 with the `notes_app` schema, if you want to follow along exactly."
---

Getting SQL onto a server is the most ordinary thing you will ask for, and it
works well without you knowing anything about how. There is exactly one
behaviour worth learning, because it decides what a half-finished script leaves
behind — and it is not visible from the outside.

## Ask what you are allowed to connect to

The agent cannot invent a host. Every server it can reach has to already be
configured, and asking is the first move of almost every session:

<div class="prompt" markdown="1">
*Which database connections do you have available?*
</div>

The agent answers that with a tool call. You will see it in the transcript; it is
not something you run:

```text
db.list_connections()
  → ["root@127.0.0.1:3310", "app_ro@db.internal:3306"]
```

<div class="callout" markdown="1">
That list comes from the shell's **secret store** — it reports the connections
whose passwords are stored, not a registry of its own. Two things follow: a
sandbox you deployed shows up without you configuring anything, and if the
secret store cannot be read then *every* connection looks unconfigured, which
reads like a broken install when it is really a credentials problem.
</div>

## Name the server however is natural

You do not have to quote the connection string exactly. Ask for
`root@127.0.0.1:3310`, or `the sandbox on 3310`, or `mariadb://root@127.0.0.1:3310`
— all of it resolves to the same stored connection. Two things are refused on
purpose:

| How you name it in the prompt | Works? |
| --- | --- |
| `root@127.0.0.1:3310` | yes — the canonical form |
| `mariadb://…` or `mysql://…` | yes — the scheme is folded away |
| `root@127.0.0.1`, when 3306 is the stored port | yes |
| with a password in it | yes, but pointless — the stored password is used, and you have leaked yours into the transcript |
| with a default schema: `…:3310/notes_app` | **no** |
| with a TLS requirement: `…?ssl-mode=REQUIRED` | **no** |

The last two ask for *more* than was configured, and rather than quietly hand
back a connection that drops what you asked for, the server refuses. If you want
a particular schema to be current, just say so in the prompt — the agent issues
a `USE`.

## Ask for results

Anything where you want to see rows back, or where one statement depends on the
last, runs as an individual statement on one open session:

<div class="prompt" markdown="1">
*Insert three users into `notes_app.user`, then show me every user with the
number of notes they have written, highest first.*
</div>

The agent will reach for the `mariadb-select` and `mariadb-aggregate-functions`
skills here. Watch for `GROUP_CONCAT` if you ask for the note titles as well —
the skill knows it truncates silently at `group_concat_max_len`, which is the
kind of detail that produces a bug report six months later.

Values you mention are sent to the server separately from the statement rather
than pasted into it, so a name with an apostrophe in it cannot break the query
or become an injection.

## Ask for a whole file to be run

Create scripts, seed data, migrations — anything multi-statement where you do
not need the results back:

<div class="prompt" markdown="1">
*Run `notes_app.sql` against the sandbox on 3310.*
</div>

The file has to be inside a directory the MCP server was given access to. If it
is not, the agent's natural fallback is to send the same SQL inline, which works
just as well — so this rarely stops anything, it just explains why the agent
sometimes pastes a script instead of pointing at it.

<div class="callout callout--warn" markdown="1">
**A script runs on one session, but it is not a transaction.** The statements
run in order on the connection's session, so whatever one of them sets is there
for the next — `SET @my_var`, a `USE notes_app`, the REST Service's
`USE REST SERVICE`. What a script does not do is undo itself: if statement five
fails, the script stops there, statements one to four have already taken effect,
and nothing is rolled back.

The tool does not raise on a failed statement either. It reports the failure in
its results, and the agent checks every entry before it tells you the script
ran. If you want that spelled out, ask for it:

*Run `notes_app.sql` against the sandbox on 3310, and tell me which statements
failed, if any.*
</div>

The one case where state does get lost is a connection that sat idle long enough
to be closed: it is reopened before the next call, and whatever the old session
held — variables, the current schema, an open transaction — is gone. Keep the
state a request depends on within that request, rather than spread across
prompts with a long pause in between.

Fully qualified names — `` `notes_app`.`note` `` rather than `note` after a
`USE` — are a good habit for the same reason: a script that names its schema
everywhere does the same thing whichever schema the session happens to be in.

## Transactions

A script can hold a transaction — `START TRANSACTION` … `COMMIT` works inside
one, because every statement runs on the same session. But if a statement fails
partway, the script stops before the `COMMIT`, and the transaction stays open on
the session until the agent rolls it back. So when the work has to be
all-or-nothing, say so, and let the agent decide how to run it:

<div class="prompt" markdown="1">
*Move every note from the "Inbox" notebook to "Archive" and delete the Inbox
notebook — in a single transaction, and roll back if anything fails.*
</div>

The `mariadb-transactions` skill covers what MariaDB does around implicit
commits, which is what turns this from a two-line answer into a correct one:
**DDL commits the open transaction**, so an `ALTER TABLE` in the middle of your
transaction silently ends it.

## Closing up

You do not have to ask for connections to be closed — they are reaped after an
idle period. The one time it matters is before deleting a sandbox: a server with
an open connection will not stop cleanly. Asking to "delete the sandbox when
you're done" covers it, because the agent closes first.

<h2 class="no-step" id="what-you-built">What you learned</h2>

- Ask what connections exist first — the agent cannot invent a host, and it
  cannot use a server nobody configured.
- Name the server loosely; just do not try to bolt a default schema or a TLS
  requirement onto it, and never put a password in the prompt.
- **A script runs on one session, but it is not a transaction.** State carries
  from one statement to the next; a failure stops the script and leaves
  everything before it in place. Ask for a transaction when you need
  all-or-nothing.

**Where to go next**

- [Explore an existing database](../browse-schema-objects/) — getting a schema
  summary without a hundred `SHOW` statements.
- [Diagnose a slow query](../diagnose-a-slow-query/) — reading a plan instead of
  guessing at an index.
