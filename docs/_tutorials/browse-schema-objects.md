---
order: 3
slug: browse-schema-objects
title: "Explore a database you did not design"
description: >-
  Point the agent at an existing MariaDB server and have it map the place out —
  schemas, tables, views, routines, columns, indexes and foreign keys — and
  answer the questions about a schema that a pile of SHOW statements cannot.
level: beginner
duration: "15 min"
area: sql
tools: ["db.list_schemas", "db.list_objects", "db.get_object_details", "db.execute_sql"]
skills: ["mariadb-show", "mariadb-information-functions"]
path_label: "First Steps, Step 3 · Operate and Optimize, Step 2"
prerequisites:
  - "A configured connection to a MariaDB server with a schema in it — the `notes_app` sandbox from [Tutorial 1](../notes-app-sandbox/) works."
---

Inheriting a database is a normal Tuesday. The agent can read a schema back as
structured detail and reason over it, which is a different thing from dumping
`SHOW CREATE TABLE` output into the conversation and hoping.

<div class="prompt" markdown="1">
*Connect to the sandbox on port 3310 and give me a map of the `notes_app`
schema: every table with its columns, primary key and foreign keys, plus any
views or stored routines. Tell me which tables have no primary key.*
</div>

That one prompt is most of this tutorial. The rest is what to expect back, and
which follow-up questions are worth asking.

## Ask for everything, not for tables

Start by finding out what is on the server at all:

<div class="prompt" markdown="1">
*What schemas are on the sandbox on port 3310?*
</div>

You never type that call yourself. The agent makes it and reports back what
came out:

```text
db.list_schemas(connection_id="…")
  → information_schema, mysql, performance_schema, sys, notes_app
```

The system schemas are always in the list. If a schema you expect is **missing**,
it is nearly always the account's privileges rather than a fault — MariaDB shows
a schema only to an account with some privilege on it, so a read-only account
scoped to one schema will see exactly one non-system schema. That is the setup
working as intended.

<div class="callout callout--tip" markdown="1">
**Say "everything in this schema", not "the tables".** Asked for tables, the
agent lists tables. Asked for everything, it fans out across views, procedures,
functions, triggers and events as well — which is what catches the view nobody
mentioned and the trigger that explains the mystery column.
</div>

## Ask for one object in detail before changing it

<div class="prompt" markdown="1">
*Show me the full definition of the `note` table — columns, types, nullability,
defaults, indexes and foreign keys.*
</div>

What comes back is structured detail rather than a `CREATE TABLE` string the
agent has to re-parse, which is why it can answer questions about the table
instead of quoting it at you. For a view or a routine you get its definition.

This is the step to insist on before *any* schema change. An `ALTER TABLE`
proposed without reading the current definition is a guess.

## Ask the questions a schema listing cannot answer

Listing objects is the wrong shape for questions *about* the schema as a whole.
Those are one query against `INFORMATION_SCHEMA`, and the agent knows it —
that is what the `mariadb-show` and `mariadb-information-functions` skills teach.
You do not have to write these; you have to know they are askable.

<div class="prompt" markdown="1">
*Which tables in `notes_app` have no primary key, what does the foreign key
graph look like, and where has the space actually gone?*
</div>

**Tables with no primary key** — the classic one, because a table without a
primary key breaks row-based replication and makes InnoDB pick a hidden one:

```sql
SELECT t.TABLE_NAME
FROM information_schema.TABLES t
LEFT JOIN information_schema.TABLE_CONSTRAINTS c
       ON  c.TABLE_SCHEMA = t.TABLE_SCHEMA
       AND c.TABLE_NAME   = t.TABLE_NAME
       AND c.CONSTRAINT_TYPE = 'PRIMARY KEY'
WHERE t.TABLE_SCHEMA = 'notes_app'
  AND t.TABLE_TYPE   = 'BASE TABLE'
  AND c.CONSTRAINT_NAME IS NULL;
```

**The foreign key graph**, which is how you work out what depends on what before
dropping anything:

```sql
SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = 'notes_app'
  AND REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY TABLE_NAME;
```

**Where the space actually went:**

```sql
SELECT TABLE_NAME,
       ROUND((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 1) AS size_mb,
       TABLE_ROWS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'notes_app'
ORDER BY DATA_LENGTH + INDEX_LENGTH DESC;
```

<div class="callout callout--warn" markdown="1">
**`TABLE_ROWS` is an estimate**, sometimes off by a large factor. It is fine for
ranking tables by rough size and useless as a count. If the number matters, ask
for a real one — *"give me actual `COUNT(*)` figures, not estimates"* — and
expect the agent to say so before running it on a big table.
</div>

## Two MariaDB-specific things to look for

When the agent maps a schema it did not write, two MariaDB features change what
the map *means*, and both are covered by skills:

- **System-versioned tables.** A table declared `WITH SYSTEM VERSIONING` keeps
  its own row history. `SELECT *` shows only current rows, so a table can be far
  larger on disk than its row count suggests, and `DELETE` does not actually
  remove anything. If a table turns out to be system-versioned, that is the
  explanation for both.
- **Invisible columns.** A column declared `INVISIBLE` is absent from
  `SELECT *` and from `INSERT` without a column list. It shows up in the object
  details and not in a query — which looks like a bug until you know.

<div class="prompt" markdown="1">
*Are any tables in this schema system-versioned? If so, show me what the `note`
table looked like a week ago.*
</div>

## Write it down

The most useful end to this exercise is a file, not a chat message:

<div class="prompt" markdown="1">
*Write everything you just found into `SCHEMA.md` — one section per table with
its columns and relationships, a diagram of the foreign keys, and a "things that
look wrong" section at the end.*
</div>

That needs the working directory on the allowed-paths list. It is also the point
at which the agent stops being a query runner and starts being useful on a
codebase you are new to.

<h2 class="no-step" id="what-you-built">What you learned</h2>

- Ask for the whole schema at once, then for one object in detail — and insist on
  the detail before any change is proposed.
- Schema-wide questions ("which tables have no primary key", "where did the space
  go") are one query, not a tour. Ask them directly.
- A missing schema is usually privileges; a surprising row count is usually
  system versioning or an estimate.

**Where to go next**

- [Diagnose a slow query](../diagnose-a-slow-query/) — now that you can read the
  schema, read the plan.
- [Version the schema with MSM](../versioned-schema-with-msm/) — put an inherited
  schema under version control before you change it.
