---
order: 8
slug: rest-endpoints
title: "Expose the Notes App over REST"
description: >-
  Put a JSON API in front of the Notes App schema with the MariaDB REST Service
  DDL — configure the metadata, create a service and a REST schema, then add a
  data mapping view per table. All of it driven from the agent over MCP.
level: intermediate
duration: "40 min"
area: rest
tools: ["db.connect", "db.execute_sql", "db.execute_sql_script", "sandbox.deploy"]
skills: ["mariadb-rest-service-create", "mariadb-rest-service-update-endpoints", "mariadb-rest-service-authorization", "mariadb-rest-service-show"]
path_label: "Build an API, Step 1"
prerequisites:
  - "[Tutorial 1](../notes-app-sandbox/) — a `notes_app` schema on a sandbox."
  - "A connection to a server where you may create schemas: `CONFIGURE REST METADATA` creates one."
---

<div class="callout callout--warn" markdown="1">
**The MariaDB REST Service is an upcoming feature.** While the REST services and
endpoints can already be defined using the MariaDB Shell, the MariaDB REST Daemon
that serves these endpoints is not yet available.
</div>

The MariaDB REST Service turns schema objects into REST endpoints that serve and
accept JSON. It is administered **entirely through SQL DDL** — an extended
`… REST …` grammar that `mariadb-shell` understands — which is what makes it a
good fit for an agent: there is no separate API, no config file, just statements
the MCP server can run. The endpoints themselves are served over HTTP by the
**REST Daemon**.

<div class="prompt" markdown="1">
*Create a SQL script that sets up the MariaDB REST Service for the `notes_app`
schema: configure the REST metadata, create a REST service with the request path
`/notesApp`, add a REST schema for `notes_app`, and add REST endpoints for its
objects — a REST data mapping view for each table, and REST procedures or
functions for any stored routines. Then run it against the sandbox.*
</div>

## Know the four steps

REST-enabling a schema always follows the same order, and skipping the fourth is
the mistake everyone makes:

1. **Configure** the REST metadata schema, once per server — `CONFIGURE REST METADATA`.
2. **Create the service** — `CREATE REST SERVICE`, the URL root of your API.
3. **Add a REST schema** — `CREATE REST SCHEMA … FROM <db_schema>`.
4. **Expose objects explicitly** — one `CREATE REST VIEW`, `CREATE REST PROCEDURE`
   or `CREATE REST FUNCTION` per object you want reachable.

<div class="callout callout--warn" markdown="1">
**A REST schema exposes nothing by itself.** Step 3 maps a database schema into
the service; it does not publish its tables. Nothing is reachable until step 4
adds an endpoint for it. This is deliberate — the default is that your data is
not on the internet.
</div>

## How the statements run

The REST grammar carries state: `USE REST SERVICE /notesApp` sets the service
that the following `CREATE REST SCHEMA` and `CREATE REST VIEW` statements belong
to, and `USE REST SCHEMA` does the same for the schema. That works whichever way
the agent sends the statements — as one script with `db.execute_sql_script`, or
one at a time with `db.execute_sql` — because both run on the same session of
the connection.

<div class="callout callout--warn" markdown="1">
**A script is not a transaction.** If the `CREATE REST VIEW` for the third table
fails, the service, the REST schema and the first two views already exist. Ask
the agent to look before it re-runs anything:

*Show me the REST services, schemas and views that exist now, then fix what
failed without recreating the rest.*

The agent answers that with `SHOW REST SERVICES` and its siblings, which the
`mariadb-rest-service-show` skill covers.
</div>

## Configure the metadata

```sql
CONFIGURE REST METADATA;
```

Run once per MariaDB instance. It creates the `mysql_rest_service_metadata`
schema, so the account needs privileges to create schemas — which is why this
tutorial uses a sandbox.

<div class="callout" markdown="1">
The metadata schema and its roles keep their upstream `mysql_rest_service_*`
names. MariaDB's REST Service is a fork of the MySQL REST Service and the
identifiers are unchanged on purpose, so existing tooling keeps working. Only the
serving component was renamed, to **REST Daemon**.
</div>

To also upgrade an existing metadata schema and enable the service in one go:

```sql
CONFIGURE REST METADATA
    ENABLED
    UPDATE IF AVAILABLE;
```

## Create the service and the REST schema

```sql
-- The REST service — the URL root path of the API
CREATE REST SERVICE /notesApp
    COMMENT "Notes App REST service";
USE REST SERVICE /notesApp;

-- Map the notes_app database schema into the service
CREATE REST SCHEMA /notes FROM `notes_app`
    COMMENT "The notes_app schema";
USE REST SCHEMA /notes;
```

<div class="callout callout--tip" markdown="1">
**New services are ENABLED but UNPUBLISHED.** An unpublished service is served
only by a REST Daemon running in development mode. That is the right default:
build all your endpoints first, then
`ALTER REST SERVICE /notesApp PUBLISHED` when the shape is settled.
</div>

## Expose the tables as data mapping views

A REST data mapping view is more than a table dump. The GraphQL-ish block
renames columns into JSON field names and, with `@UNNEST`, **flattens related
tables into one document** — so a client fetches a note with its tags in a single
request instead of three:

```sql
CREATE REST VIEW /note
AS `notes_app`.`note` {
    id:        id        @KEY @SORTABLE,
    title:     title     @SORTABLE,
    body:      body,
    createdAt: created_at @SORTABLE,
    noteTag: notes_app.note_tag @UNNEST {
        tag: notes_app.tag @UNNEST {
            name: name
        }
    }
}
AUTHENTICATION REQUIRED;
```

The annotations the agent should be using, and what each one buys:

| Annotation | Effect |
| --- | --- |
| `@KEY` | Marks the identifying column — required for row-level `GET /note/<id>`, `PUT` and `DELETE`. |
| `@SORTABLE` | Allows the client to order by this field. Opt-in, per field. |
| `@UNNEST` | Flattens a related table into the parent document. |
| CRUD flags | Which of create / read / update / delete the endpoint permits. Read-only unless you say otherwise. |

<div class="prompt" markdown="1">
*Make `/note` read-only for now, but allow create and update on `/notebook`.
And do not expose the `user` table's `email` column at all.*
</div>

Leaving a field out of the mapping block is how you keep it out of the API. That
is a better answer than a view, because there is nothing to keep in sync.

## Add authentication before you publish

An endpoint marked `AUTHENTICATION REQUIRED` needs an auth app and a user behind
it. The `mariadb-rest-service-authorization` skill covers auth apps, REST users,
REST roles, and the `GRANT REST` / `REVOKE REST` statements that connect them to
endpoints.

<div class="prompt" markdown="1">
*Create a REST auth app for `/notesApp` using MRS-native authentication, add a
REST role that can read `/notes/note` but not write it, and create a test user
with that role.*
</div>

## Verify with SHOW REST

`SHOW REST` is how you confirm what actually exists, rather than what the script
claimed to create:

```sql
SHOW REST SERVICES;
SHOW REST SCHEMAS;
SHOW REST VIEWS;
SHOW REST PROCEDURES;
SHOW REST FUNCTIONS;
```

And for one object's full definition — the fastest way to see whether an
annotation landed:

```sql
SHOW CREATE REST VIEW /notes/note;
```

<div class="prompt" markdown="1">
*Run all the SHOW REST commands against the sandbox and confirm `/notesApp`
exists with an endpoint for every table.*
</div>

## Publish

```sql
ALTER REST SERVICE /notesApp PUBLISHED;
```

Serving those endpoints over HTTP is the REST Daemon's job, and standing one up
is outside this tutorial. Everything above is complete and inspectable without
it — the metadata *is* the API definition.

## Ship it with the schema

If the schema is an MSM project ([Tutorial 6](../versioned-schema-with-msm/)),
the REST setup does not belong in a separate script you have to remember to run.
**MSM section 180 exists for exactly this**: optional MariaDB REST Service
endpoints, versioned and deployed alongside the schema they expose.

<div class="prompt" markdown="1">
*Move the REST DDL into section 180 of the MSM development script, prepare a
patch release, and deploy it — so the endpoints ship with the schema version
that defines them.*
</div>

<h2 class="no-step" id="what-you-built">What you built</h2>

- A `/notesApp` REST service with a data mapping view per table, related rows
  flattened with `@UNNEST`, and per-field control over what is exposed.
- `CONFIGURE` → `CREATE REST SERVICE` → `CREATE REST SCHEMA` → **one endpoint per
  object**, in that order, with nothing reachable until the last step.
- REST DDL run on the connection's session, as a script or statement by
  statement — `USE REST SERVICE` and `USE REST SCHEMA` carry over either way.

**Where to go next**

- [Ship a schema upgrade](../ship-a-schema-upgrade/) — put the REST DDL in
  section 180 and version it properly.
- [Migrate from MySQL](../mysql-to-mariadb-migration/) — the other end-to-end
  automation in the plugin.
