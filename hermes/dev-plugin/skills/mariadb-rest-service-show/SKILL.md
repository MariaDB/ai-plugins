---
name: mariadb-rest-service-show
description: "Browse and inspect existing MariaDB REST Service objects with SHOW REST commands — list services, schemas, data mapping views, procedures, functions, scripts, content sets/files, auth apps and vendors, users, roles, grants, REST Daemons and metadata schemas; check service status; list the columns a table can expose; dump the DDL (or JSON) of any object with SHOW CREATE REST. Use when asked to list, discover, inspect, audit or reverse-engineer existing REST endpoints, or to see the CREATE statement behind a REST object on MariaDB."
---

# Browsing a MariaDB REST Service with SHOW REST

`SHOW REST ...` statements list the REST objects that exist; `SHOW CREATE REST
...` reproduces the DDL for a single object. Both are read-only and run in
**`mariadb-shell`**. Use them to discover what is deployed, audit access, or
recover the exact statement that created an endpoint before altering it.

Assume MariaDB 11.8 if not told otherwise.

## Set a default context first (optional)

Most `SHOW` statements take an explicit `ON`/`FROM SERVICE ...` (and `SCHEMA
...`) clause. Setting a default context with `USE` lets you omit it on the
statements that follow:

```sql
USE REST SERVICE /myService;
USE REST SCHEMA /sakila;
-- or both at once:
USE REST SERVICE /myService SCHEMA /sakila;
```

## Overall status

```sql
SHOW REST STATUS;            -- synonym: SHOW REST METADATA STATUS
SHOW REST METADATA SCHEMAS;  -- the metadata schemas this account can see
SHOW REST DAEMONS;           -- the REST Daemon instances serving the services
```

`SHOW REST STATUS` reports whether the metadata schema is configured and
enabled, the number of enabled services, the current and available metadata
version, whether it can be updated, and which metadata schema the session uses.

The metadata schema is `mariadb_rest_service`, or one with a prefix/postfix such
as `acme_mariadb_rest_service`. When an account sees several but not
`mariadb_rest_service`, REST statements fail until you pick one:
`USE REST METADATA SCHEMA acme_mariadb_rest_service;`

`SHOW REST DAEMONS` lists each instance's `id` (a UUID), address, version, last
check-in, whether it is `active` (checked in within 10 s) and its `developer`.
`SHOW REST SERVICES FOR DAEMON '<id>'` lists what one instance serves.

## Listing objects

Work top-down: services → schemas → objects. The service/schema clause is
optional once a default context is set with `USE`.

```sql
-- All REST services (or only those linked to an auth app)
SHOW REST SERVICES;
SHOW REST SERVICES FOR AUTH APP "MRS";

-- Schemas of a service
SHOW REST SCHEMAS FROM SERVICE /myService;

-- Data mapping views, procedures and functions of a schema
SHOW REST VIEWS FROM SERVICE /myService SCHEMA /sakila;
SHOW REST PROCEDURES FROM SERVICE /myService SCHEMA /sakila;
SHOW REST FUNCTIONS FROM SERVICE /myService SCHEMA /sakila;
SHOW REST SCRIPTS FROM SERVICE /myService SCHEMA /sales;   -- MRS scripts

-- Static content
SHOW REST CONTENT SETS FROM SERVICE /myService;
SHOW REST CONTENT FILES FROM SERVICE /myService CONTENT SET /myContentSet;
```

`ON` and `FROM` are interchangeable in these statements (`... ON SERVICE ...`
== `... FROM SERVICE ...`). After a `USE`, the clause can be dropped entirely,
e.g. `SHOW REST VIEWS;` once both a service and a schema are current.

To see what a table, view or routine *could* expose — columns, foreign-key
references in both directions, or routine parameters and return type:

```sql
SHOW REST COLUMNS FROM sakila.city;
SHOW REST COLUMNS FROM PROCEDURE sakila.film_in_stock;
```

## Listing authorization objects

```sql
-- Auth apps linked to a service, all auth apps, and the available vendors
SHOW REST AUTH APPS FROM SERVICE /myService;
SHOW REST AUTH APPS ON ANY SERVICE;
SHOW REST AUTH VENDORS;

-- REST users (of a service's auth apps, or of one auth app); never passwords
SHOW REST USERS ON SERVICE /myService;
SHOW REST USERS FOR AUTH APP "MRS";

-- Roles (optionally scoped, or filtered to a user's granted roles)
SHOW REST ROLES;
SHOW REST ROLES ON SERVICE /myService;
SHOW REST ROLES ON ANY SERVICE;
SHOW REST ROLES FOR "alice"@"MRS";

-- The privileges granted to a role
SHOW REST GRANTS FOR "reader";
SHOW REST GRANTS FOR "reader" ON SERVICE /myService;
```

See `mariadb-rest-service-authorization` for what these roles and grants mean.

## Dumping DDL with SHOW CREATE REST

`SHOW CREATE REST ...` returns the DDL statement that recreates a single object —
the reliable way to see an endpoint's exact definition (field mapping, CRUD
flags, options) before editing or cloning it.

```sql
-- Service; INCLUDING ... ENDPOINTS also emits the nested endpoint DDL:
-- SCHEMA (= DATABASE) for schemas and objects, ALL to add content sets and scripts
SHOW CREATE REST SERVICE /myService;
SHOW CREATE REST SERVICE /myService INCLUDING SCHEMA ENDPOINTS;
SHOW CREATE REST SERVICE /myService INCLUDING ALL ENDPOINTS;

SHOW CREATE REST SCHEMA /sakila FROM SERVICE /myService;

SHOW CREATE REST VIEW /city ON SERVICE /myService SCHEMA /sakila;
SHOW CREATE REST PROCEDURE /filmInStock ON SERVICE /myService SCHEMA /sakila;
SHOW CREATE REST FUNCTION /maxRate ON SERVICE /myService SCHEMA /sakila;

SHOW CREATE REST CONTENT SET /myContentSet FROM SERVICE /myService;
SHOW CREATE REST CONTENT FILE `/index.html` FROM SERVICE /myService CONTENT SET /myContentSet;

-- Authorization objects (auth apps are not per service)
SHOW CREATE REST AUTH APP "MRS";
SHOW CREATE REST ROLE "editor" ON SERVICE /myService;
SHOW CREATE REST USER "alice"@"MRS";
```

`SHOW CREATE REST VIEW` is especially useful: creating a REST view without an
explicit GraphQL block auto-expands to all columns, and `SHOW CREATE REST VIEW`
reveals the generated field mapping so you can copy and refine it.

Request paths with characters other than letters, digits, `_` and `$` (such as
the `.` in `/index.html`) must be back-tick quoted.

### JSON output

Append `FORMAT=JSON` to any `SHOW CREATE REST ...`, to every list statement
above except `SHOW REST GRANTS`, and to `SHOW REST STATUS`, `SHOW REST COLUMNS`
and `SHOW REST DAEMONS`, to get a JSON document (lists: one row holding a JSON
array) instead of DDL or a table — handy for tools. Ids are UUID strings; secrets and passwords are never
returned.

```sql
SHOW CREATE REST VIEW /city ON SERVICE /myService SCHEMA /sakila FORMAT=JSON;
SHOW REST VIEWS ON SERVICE /myService SCHEMA /sakila FORMAT=JSON;
```

## Typical browse workflow

```sql
SHOW REST STATUS;                                    -- is MRS configured/enabled?
SHOW REST SERVICES;                                  -- pick a service
USE REST SERVICE /myService;
SHOW REST SCHEMAS;                                   -- its schemas
SHOW REST VIEWS FROM SCHEMA /sakila;                 -- its views
SHOW CREATE REST VIEW /city FROM SCHEMA /sakila;     -- inspect one in detail
```

## See Also

- `mariadb-rest-service-create` — creating the objects these statements list.
- `mariadb-rest-service-update-endpoints` — using `SHOW CREATE REST` output as the baseline before `ALTER`/`DROP`.
- `mariadb-rest-service-authorization` — meaning of auth apps, roles and grants.
- `mariadb-show` — the underlying MariaDB `SHOW` statements.
