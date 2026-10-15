---
name: mariadb-rest-service-drop
description: "Remove MariaDB REST Service objects with DROP REST statements — drop a REST service, schema, data mapping view, procedure, function, content set/file, auth app, user, role or stale REST Daemon registration, using IF EXISTS to avoid errors. Use when asked to delete, remove, tear down or clean up existing REST endpoints, auth apps, users or roles on MariaDB (dropping the REST metadata only, never the underlying database object)."
---

# Removing MariaDB REST Service Objects with DROP REST

`DROP REST ...` statements remove REST objects and their metadata. They run in
**`mariadb-shell`**.

Assume MariaDB 11.8 if not told otherwise.

## Two rules that always apply

1. **DROP REST removes only the REST endpoint/metadata — never the underlying
   database object.** `DROP REST VIEW /city` deletes the REST endpoint; the
   `sakila.city` table is untouched. The same holds for procedures, functions and
   schemas: the database schema and its routines remain.
2. **Dropping a container drops everything beneath it.** Dropping a REST service
   removes all its schemas and their endpoints; dropping a REST schema removes all
   its views/procedures/functions. There is no `CASCADE`/`RESTRICT` keyword — the
   hierarchical removal is implicit.

Every `DROP REST` statement accepts an optional `IF EXISTS`, which turns a
"does not exist" error into a no-op (a note). Prefer it in scripts. It covers
only the object itself: a missing parent service or schema named in `FROM ...`
is still an error.

## Endpoint objects

```sql
-- A single data mapping view / procedure / function
DROP REST VIEW IF EXISTS /city FROM SERVICE /myService SCHEMA /sakila;
DROP REST PROCEDURE IF EXISTS /filmInStock FROM SERVICE /myService SCHEMA /sakila;
DROP REST FUNCTION IF EXISTS /maxRate FROM SERVICE /myService SCHEMA /sakila;
```

The `FROM SERVICE ... SCHEMA ...` selector can be omitted when a default context
has been set with `USE REST SERVICE /myService SCHEMA /sakila` (see
`mariadb-rest-service-show`).

## Schema and service

```sql
-- A REST schema (drops the views/procedures/functions it contains)
DROP REST SCHEMA IF EXISTS /sakila FROM SERVICE /myService;

-- A whole REST service (drops all its schemas, endpoints and roles)
DROP REST SERVICE IF EXISTS /myService;
```

## Static content

```sql
DROP REST CONTENT FILE IF EXISTS `/index.html`
    FROM SERVICE /myService CONTENT SET /myContentSet;

DROP REST CONTENT SET IF EXISTS /myContentSet FROM SERVICE /myService;
```

Back-tick quote request paths with characters other than letters, digits, `_`
and `$`, such as the `.` in `/index.html`.

## Authorization objects

```sql
-- An auth app: also unlinks it from every service and drops its REST users
DROP REST AUTH APP IF EXISTS "MRS";

-- A REST user of an auth app
DROP REST USER IF EXISTS "alice"@"MRS";

-- A REST role (scope with ON SERVICE / ON ANY SERVICE when ambiguous)
DROP REST ROLE IF EXISTS "reader" ON SERVICE /myService;
DROP REST ROLE IF EXISTS "globalRole" ON ANY SERVICE;
```

See `mariadb-rest-service-authorization` for the auth app / user / role model.

## REST Daemon registrations

Each MariaDB REST Daemon instance registers itself in the REST metadata. To
remove one that no longer runs (with its status reports and log entries), take
its UUID from `SHOW REST DAEMONS` and drop it; a running instance registers
again when it restarts:

```sql
SHOW REST DAEMONS;
DROP REST DAEMON IF EXISTS '0199a1b2-6c3e-7d41-9a0f-2b8c4d5e6f70';
```

## Removing MRS from a server

There is no `DROP REST METADATA`. To remove the MariaDB REST Service entirely,
drop the metadata schema with plain SQL — this deletes **all** REST services,
REST users and REST roles on the server (your application schemas, and the
MariaDB `mariadb_rest_service_*` roles, stay):

```sql
DROP SCHEMA mariadb_rest_service;
```

Use the prefixed/postfixed name (e.g. `acme_mariadb_rest_service`) for a
per-customer metadata schema. Do this only when explicitly asked.

## Before you drop

- Dumping the DDL first lets you recreate the object if the drop was a mistake:
  `SHOW CREATE REST VIEW /city ON SERVICE /myService SCHEMA /sakila;` (see
  `mariadb-rest-service-show`).
- If the removal is only temporary, prefer disabling over dropping — `ALTER REST
  ... DISABLED` (or `PRIVATE` for schemas/objects) keeps the definition and is
  reversible, whereas a drop is permanent. See
  `mariadb-rest-service-update-endpoints`.

## See Also

- `mariadb-rest-service-show` — dump an object's DDL with `SHOW CREATE REST` before dropping it.
- `mariadb-rest-service-update-endpoints` — disable/unpublish as a reversible alternative to dropping.
- `mariadb-rest-service-create` — recreating dropped objects.
- `mariadb-rest-service-authorization` — auth apps, users and roles.
- `mariadb-drop-table` — the underlying database DROP (which DROP REST does *not* perform).
