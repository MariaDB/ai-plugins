---
name: mariadb-rest-service-create
description: "Create a MariaDB REST Service for a database schema — configure the REST metadata schema, create the REST service, add a REST schema, and expose tables/views as REST data mapping views and stored procedures/functions as REST procedures/functions. Use when asked to REST-enable a MariaDB schema, publish tables/views/routines over HTTP, or write CREATE REST SERVICE / SCHEMA / VIEW / PROCEDURE / FUNCTION DDL."
---

# Creating a MariaDB REST Service

The MariaDB REST Service exposes database schema objects (tables, views, stored
procedures and functions) as REST endpoints that serve and accept JSON. It is a
fork of the MySQL REST Service and is administered entirely through SQL DDL
statements run in **`mariadb-shell`**, which understands the extended
`... REST ...` grammar. The endpoints themselves are served over HTTP(S) by the
**REST Daemon**.

Assume MariaDB 11.8 and the latest REST Service metadata schema if not told
otherwise. Comment each REST object you create to describe its purpose.

## The four steps

REST-enabling a schema always follows the same order. Each step has its own
statement; run them in `mariadb-shell`:

1. **Configure** the REST metadata schema once per server — `CONFIGURE REST METADATA`.
2. **Create the service** — `CREATE REST SERVICE`, the URL root of your API.
3. **Add a REST schema** — `CREATE REST SCHEMA ... FROM <db_schema>`, mapping a
   database schema into the service. *This alone exposes nothing.*
4. **Expose objects explicitly** — one `CREATE REST VIEW` / `CREATE REST PROCEDURE`
   / `CREATE REST FUNCTION` per table, view or routine you want reachable.

> A REST schema does **not** auto-expose its database objects. Nothing is
> reachable until you add a REST view/procedure/function for it in step 4.

### Canonical end-to-end script

```sql
-- One-time server configuration of the REST metadata schema
CONFIGURE REST METADATA;

-- The REST service — the URL root path of the API
CREATE REST SERVICE /myService
    COMMENT "Sakila demo REST service";
USE REST SERVICE /myService;

-- Map the `sakila` database schema into the service
CREATE REST SCHEMA /sakila FROM `sakila`
    COMMENT "The sakila schema";
USE REST SCHEMA /sakila;

-- Expose the `actor` table, flattening its films into each actor document
CREATE REST VIEW /actor
AS `sakila`.`actor` {
    actorId: actor_id @SORTABLE @KEY,
    firstName: first_name,
    lastName: last_name,
    lastUpdate: last_update,
    filmActor: sakila.film_actor @UNNEST {
        film: sakila.film @UNNEST {
            title: title
        }
    }
}
AUTHENTICATION REQUIRED;
```

New services are created **ENABLED but UNPUBLISHED**. An unpublished service is
only served by a REST Daemon running in development mode; publish it with
`ALTER REST SERVICE /myService PUBLISHED` once all endpoints exist (see the
`mariadb-rest-service-update-endpoints` skill).

## Step 1 — CONFIGURE REST METADATA

Run once per MariaDB instance (or InnoDB Cluster/Set). It creates the
`mysql_rest_service_metadata` database schema, so the account running it needs
privileges to create schemas.

```sql
CONFIGURE REST METADATA;
```

To also upgrade an existing metadata schema to the latest version, and to enable
the service after configuring:

```sql
CONFIGURE REST METADATA
    ENABLED
    UPDATE IF AVAILABLE;
```

Global options are set as a JSON document via `OPTIONS` (add `MERGE` before
`OPTIONS` to merge with, rather than overwrite, existing options). Common keys:

- `authentication.throttling` — brute-force protection (`perAccount` / `perHost`
  limits, `blockWhenAttemptsExceededInSeconds`).
- `gtid.cache` — the REST Daemon's GTID cache (`enable`, `refreshRate`,
  `refreshWhenIncreasesBy`) for read-your-writes across replicas.
- `responseCache.maxCacheSize` / `fileCache.maxCacheSize` — in-memory caches.

```sql
CONFIGURE REST METADATA
    ENABLED
    OPTIONS {
        "authentication": {
            "throttling": {
                "perAccount": {
                    "minimumTimeBetweenRequestsInMs": 1500,
                    "maximumAttemptsPerMinute": 5
                },
                "blockWhenAttemptsExceededInSeconds": 120
            }
        }
    };
```

## Step 2 — CREATE REST SERVICE

Create one REST service per application. Each has its own options, authentication
apps and users.

```sql
CREATE OR REPLACE REST SERVICE /myService
    COMMENT "A simple REST service";
```

- Use `CREATE OR REPLACE REST SERVICE` to (re)create idempotently, or
  `CREATE REST SERVICE IF NOT EXISTS` to skip when present. The two forms are
  mutually exclusive.
- The request path (`/myService`) is the URL context root. Back-tick quote it if
  it contains special characters.
- `USE REST SERVICE /myService;` makes it the default target so later statements
  can omit `ON SERVICE`.

Key options (repeatable, in any order):

| Option | Purpose |
| --- | --- |
| `ENABLED` / `DISABLED` | Service state (default `ENABLED`). |
| `PUBLISHED` / `UNPUBLISHED` | Whether all REST Daemons serve it (default `UNPUBLISHED`). |
| `PROTOCOL HTTP` / `HTTPS` | External protocol (default HTTPS — keep it). |
| `AUTHENTICATION PATH ... REDIRECTION ... VALIDATION ... PAGE CONTENT ...` | Auth workflow paths (see `mariadb-rest-service-authorization`). |
| `ADD AUTH APP "name"` | Link an auth app (see `mariadb-rest-service-authorization`). |
| `COMMENT "..."` | Description, max 512 chars. |
| `METADATA { ... }` | Arbitrary JSON for front ends. |
| `OPTIONS { ... }` | Service JSON options (below). |

Service `OPTIONS` JSON keys include `headers` (e.g. CORS
`Access-Control-Allow-*`), `http.allowedOrigin` (`*` / `null` / `<origin>` /
`auto`), `logging`, `returnInternalErrorDetails` (dev only — off in production),
`includeLinksInResults`, and `sqlQuery.timeout` (ms per DB operation, default
2000). Example:

```sql
CREATE OR REPLACE REST SERVICE /myTestService
    COMMENT "A simple REST service"
    AUTHENTICATION
        PATH "/authentication"
        REDIRECTION DEFAULT
        VALIDATION DEFAULT
        PAGE CONTENT DEFAULT
    OPTIONS {
        "headers": {
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With, Origin, X-Auth-Token",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS"
        },
        "http": { "allowedOrigin": "auto" },
        "returnInternalErrorDetails": true,
        "includeLinksInResults": false
    };
```

## Step 3 — CREATE REST SCHEMA

A REST schema maps one database schema into a REST service. It is a prerequisite
for exposing that schema's objects, but exposes nothing by itself.

```sql
CREATE OR REPLACE REST SCHEMA /sakila ON SERVICE /myService
    FROM `sakila`
    COMMENT "The sakila schema";
USE REST SCHEMA /sakila;
```

- `FROM \`sakila\`` is the underlying database schema (back-tick quoted).
- Omit `ON SERVICE ...` after `USE REST SERVICE`.
- State option is `ENABLED` / `DISABLED` / `PRIVATE`. `PRIVATE` blocks public
  HTTPS access but keeps the schema reachable from internal MRS scripts.
- `ITEMS PER PAGE <n>` sets the default page size for its objects.
- Also supports `OPTIONS`, `COMMENT`, `METADATA`.

## Step 4 — Expose database objects

### Tables and views → CREATE REST VIEW

`CREATE REST DATA MAPPING VIEW` (the `DATA MAPPING` words are optional) turns a
table or view into a JSON endpoint. The JSON shape is defined with an extended
GraphQL block. Omitting the block exposes every column as a flat object:

```sql
CREATE OR REPLACE REST VIEW /city
ON SERVICE /myService SCHEMA /sakila
AS `sakila`.`city`
AUTHENTICATION REQUIRED;
```

With an explicit field list you rename fields and annotate them:

```sql
CREATE REST VIEW /city
ON SERVICE /myService SCHEMA /sakila
AS `sakila`.`city` {
    cityId: city_id @SORTABLE @KEY,
    city: city,
    countryId: country_id,
    lastUpdate: last_update
}
AUTHENTICATION REQUIRED;
```

**Field annotations** (inside the block, after `restField: db_column`):

- `@SORTABLE` — the field may be used in `$orderby`.
- `@KEY` — marks a document-identity column. Required when the table has no
  primary key, or for a database view (map **every** PK column of every
  underlying table). With a PK, the PK is the identifier automatically; a
  composite PK yields a comma-joined id, e.g. `GET .../myTable/1,2`.
- `@NOCHECK` — exclude the field from the ETag concurrency checksum.
- `@NOFILTERING` — the field cannot be used in filters.
- `@ROWOWNERSHIP` — marks the row-ownership column for user-owned data (see
  `mariadb-rest-service-authorization`).
- `@UNNEST` — merge a referenced 1-to-1 / N-to-1 table's fields into this level
  instead of nesting them (see below).
- `@DATATYPE("...")` — override the mapped data type.

**CRUD operations** are controlled with object-level annotations after the
`AS \`schema\`.\`table\`` clause. Only READ (SELECT) is enabled by default; add
the others explicitly:

```sql
CREATE OR REPLACE REST VIEW /city
AS `sakila`.`city` @INSERT @UPDATE @DELETE
AUTHENTICATION REQUIRED;
```

| Annotation | CRUD | SQL |
| --- | --- | --- |
| (default) | READ | SELECT |
| `@INSERT` | CREATE | INSERT |
| `@UPDATE` | UPDATE | UPDATE |
| `@DELETE` | DELETE | DELETE |

Use `@NOINSERT` / `@NOUPDATE` / `@NODELETE` / `@NOCHECK` to disable operations,
and `@CHECK` for ETag checking.

**Nested and unnested relationships.** Related tables (declared with PK/FK/UK
constraints) can be embedded. A referenced table produces a nested JSON object
(1-to-1 / N-to-1) or array (1-to-N); adding `@UNNEST` flattens a 1-to-1 / N-to-1
reference into the parent level:

```sql
CREATE OR REPLACE REST VIEW /city
ON SERVICE /myService SCHEMA /sakila
AS `sakila`.`city` {
    cityId: city_id @SORTABLE,
    city: city,
    countryId: country_id,
    lastUpdate: last_update,
    country: sakila.country {
        countryId: country_id @SORTABLE,
        country: country,
        lastUpdate: last_update
    }
}
AUTHENTICATION REQUIRED;
```

Object options after the block: `AUTHENTICATION [NOT] REQUIRED`,
`ENABLED`/`DISABLED`/`PRIVATE`, `ITEMS PER PAGE <n>`, `MEDIA TYPE "..."` /
`AUTODETECT`, `FORMAT FEED|ITEM|MEDIA`, `COMMENT`, `METADATA`, and `OPTIONS`.
Set `AUTHENTICATION REQUIRED` by default; use `AUTHENTICATION NOT REQUIRED` only
for endpoints that are intentionally public.

### Stored procedures → CREATE REST PROCEDURE

```sql
CREATE OR REPLACE REST PROCEDURE /filmInStock
ON SERVICE /myService SCHEMA /sakila
AS sakila.film_in_stock
PARAMETERS MyServiceSakilaFilmInStockParams {
    pFilmId: p_film_id @IN,
    pStoreId: p_store_id @IN,
    pFilmCount: p_film_count @OUT
}
RESULT MyServiceSakilaFilmInStock {
    inventoryId: inventory_id @DATATYPE("int")
};
```

- Parameters use `@IN` / `@OUT` / `@INOUT`.
- Declare one `RESULT <name> { ... }` block per result set the procedure returns.
- The simplest form omits parameters and results: `CREATE OR REPLACE REST
  PROCEDURE /report ON SERVICE /myService SCHEMA /sakila AS sakila.rewards_report;`
- Add `FORCE` (after the `AS ...` routine name) to create the endpoint even when
  the underlying stored procedure does not yet exist.

### Stored functions → CREATE REST FUNCTION

Same shape as procedures, with a single `RESULT` for the return value:

```sql
CREATE OR REPLACE REST FUNCTION /maxFilmRentalRate
ON SERVICE /myService SCHEMA /sakila
AS sakila.get_max_rental_rate
PARAMETERS MyServiceParams {
    pCategory: p_category @IN
}
RESULT MyServiceResult {
    maxRate: max_rate @DATATYPE("decimal")
};
```

`FORCE` works the same as for procedures.

## Automatic privilege grants

When you create or alter a REST object, `mariadb-shell` automatically grants the
privileges the REST Daemon needs (via the `mysql_rest_service_data_provider`
role) to read/write the referenced database object. If a stored routine touches
other tables or calls other routines, add those grants through the object's
`OPTIONS.grants` list (or set `OPTIONS.disableAutomaticGrants` to manage them
fully yourself).

## Verify what you created

```sql
SHOW REST SERVICES;
SHOW REST SCHEMAS FROM SERVICE /myService;
SHOW REST VIEWS FROM SERVICE /myService SCHEMA /sakila;
SHOW REST PROCEDURES FROM SERVICE /myService SCHEMA /sakila;
SHOW CREATE REST VIEW /city ON SERVICE /myService SCHEMA /sakila;
SHOW REST STATUS;
```

## See Also

- `mariadb-rest-service-update-endpoints` — altering, renaming, publishing and dropping REST endpoints.
- `mariadb-rest-service-authorization` — authentication apps, users, roles and REST privileges.
- `mariadb-create-view`, `mariadb-create-procedure`, `mariadb-create-function` — the underlying database objects.
- `mariadb-grant` — the SQL privileges behind the automatic REST grants.
