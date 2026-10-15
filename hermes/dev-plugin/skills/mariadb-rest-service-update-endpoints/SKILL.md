---
name: mariadb-rest-service-update-endpoints
description: "Update MariaDB REST Service endpoints — alter a REST service, schema, data mapping view, procedure or function; rename request paths; enable/disable; publish/unpublish a service; add/remove auth apps; merge JSON options; and drop endpoints. Use when asked to change, rename, publish, re-configure or remove existing REST SERVICE / SCHEMA / VIEW / PROCEDURE / FUNCTION endpoints on MariaDB."
---

# Updating MariaDB REST Service Endpoints

Existing MariaDB REST Service endpoints are modified with `ALTER REST ...`
statements and removed with `DROP REST ...` statements, run in **`mariadb-shell`**.
Each `ALTER` accepts the same options as the matching `CREATE` (see the
`mariadb-rest-service-create` and `mariadb-rest-service-authorization` skills);
this skill covers what is specific to *changing* endpoints.

Assume MariaDB 11.8 if not told otherwise.

## Inspect before you change

`ALTER` overwrites the options you specify. Before altering, dump the current
definition so you know the baseline and can reproduce anything you must keep:

```sql
SHOW CREATE REST SERVICE /myService INCLUDING SCHEMA ENDPOINTS;
SHOW CREATE REST SCHEMA /sakila FROM SERVICE /myService;
SHOW CREATE REST VIEW /city ON SERVICE /myService SCHEMA /sakila;
SHOW CREATE REST PROCEDURE /filmInStock ON SERVICE /myService SCHEMA /sakila;
SHOW CREATE REST FUNCTION /maxRate ON SERVICE /myService SCHEMA /sakila;
```

`SHOW REST SERVICES`, `SHOW REST SCHEMAS`, `SHOW REST VIEWS`,
`SHOW REST PROCEDURES` and `SHOW REST FUNCTIONS` list what exists.

## MERGE vs. overwrite for JSON options

The single most common mistake when altering: a bare `OPTIONS { ... }` **replaces
all existing options**. To change one key and keep the rest, prefix with `MERGE`:

```sql
-- Replaces the entire options document (drops any keys not listed)
ALTER REST SERVICE /myService
    OPTIONS { "returnInternalErrorDetails": false };

-- Merges: only returnInternalErrorDetails changes, other options are preserved
ALTER REST SERVICE /myService
    MERGE OPTIONS { "returnInternalErrorDetails": false };
```

## Renaming: NEW REQUEST PATH

Every `ALTER REST ...` supports `NEW REQUEST PATH` to change the endpoint's URL
segment. This is the only way to rename an endpoint (there is no separate rename
statement):

```sql
ALTER REST SCHEMA /sakila ON SERVICE /myService
    NEW REQUEST PATH /movies;

ALTER REST VIEW /city ON SERVICE /myService SCHEMA /movies
    NEW REQUEST PATH /cities;
```

## ALTER REST SERVICE

```sql
alterRestServiceStatement:
    ALTER REST SERVICE serviceRequestPath (NEW REQUEST PATH newServiceRequestPath)?
        restServiceOptions?
```

Change a comment, state, protocol, auth settings, options, or add/remove auth
apps. Examples:

```sql
-- Update the description
ALTER REST SERVICE /myService
    COMMENT "A simple, improved REST service";

-- Enable / disable the whole service
ALTER REST SERVICE /myService DISABLED;
ALTER REST SERVICE /myService ENABLED;

-- Link or unlink authentication apps
ALTER REST SERVICE /myService ADD AUTH APP "MRS";
ALTER REST SERVICE /myService REMOVE AUTH APP "MRS" IF EXISTS;
```

### Publishing a service

New services are `UNPUBLISHED` (served only by a REST Daemon in development
mode). Once all schemas and endpoints exist, publish so every REST Daemon serves
it — and unpublish to pull it back:

```sql
ALTER REST SERVICE /myService PUBLISHED;
ALTER REST SERVICE /myService UNPUBLISHED;
```

## ALTER REST SCHEMA

Repoint the schema at a different database schema (`FROM`), change state,
page size, options, comment or metadata, or rename it:

```sql
ALTER REST SCHEMA /sakila ON SERVICE /myService
    ITEMS PER PAGE 50
    COMMENT "Sakila, paged 50 at a time";

ALTER REST SCHEMA /sakila ON SERVICE /myService PRIVATE;
```

## ALTER REST VIEW

`ALTER REST DATA MAPPING VIEW` changes the field mapping (GraphQL block), CRUD
annotations, request path or object options. Re-supply the `CLASS`/GraphQL block
when changing fields:

```sql
ALTER REST VIEW /city
ON SERVICE /myService SCHEMA /sakila
FROM `sakila`.`city` AS MyServiceSakilaCity {
    cityId: city_id @SORTABLE @KEY,
    city: city
};

-- Toggle CRUD and auth without touching fields
ALTER REST VIEW /city ON SERVICE /myService SCHEMA /sakila
    @INSERT @UPDATE @NODELETE;

ALTER REST VIEW /city ON SERVICE /myService SCHEMA /sakila
    AUTHENTICATION NOT REQUIRED;
```

Field/CRUD annotations (`@SORTABLE`, `@KEY`, `@UNNEST`, `@INSERT`, `@NOUPDATE`,
…) are described in `mariadb-rest-service-create`.

## ALTER REST PROCEDURE / FUNCTION

Change parameters, result sets, request path or options. Re-declare the
`PARAMETERS` and `RESULT` blocks you want in effect:

```sql
ALTER REST PROCEDURE /filmInStock
ON SERVICE /myService SCHEMA /sakila
NEW REQUEST PATH /filmStock
PARAMETERS MyServiceSakilaFilmInStockParams {
    pFilmId: p_film_id @IN,
    pStoreId: p_store_id @IN,
    pFilmCount: p_film_count @OUT
};

ALTER REST FUNCTION /maxRate
ON SERVICE /myService SCHEMA /sakila
    ITEMS PER PAGE 25;
```

## ALTER REST AUTH APP / USER

```sql
ALTER REST AUTH APP "MRS" NEW NAME "MRSAuth";
ALTER REST AUTH APP "MRS" DISABLED;

ALTER REST USER "alice"@"MRS" IDENTIFIED BY "new-password";
ALTER REST USER "alice"@"MRS" ACCOUNT LOCK;
```

See `mariadb-rest-service-authorization` for the auth app / user / role model.

## Dropping endpoints

Every object has a `DROP REST ...` with optional `IF EXISTS`:

```sql
DROP REST VIEW IF EXISTS /city FROM SERVICE /myService SCHEMA /sakila;
DROP REST PROCEDURE IF EXISTS /filmInStock FROM SERVICE /myService SCHEMA /sakila;
DROP REST FUNCTION IF EXISTS /maxRate FROM SERVICE /myService SCHEMA /sakila;
DROP REST SCHEMA IF EXISTS /sakila FROM SERVICE /myService;
DROP REST SERVICE IF EXISTS /myService;
```

Dropping a REST object only removes the REST endpoint and its metadata — it never
touches the underlying database table, view or routine. Dropping a REST schema
or service drops all endpoints beneath it.

## Cloning a service

To duplicate a service (all endpoints and roles) under a new request path:

```sql
CLONE REST SERVICE /myService NEW REQUEST PATH /myServiceCopy;
```

## Disable vs. drop

Prefer disabling over dropping when a change is temporary — a disabled service,
schema or object keeps its definition and can be re-enabled, whereas a drop is
permanent. `PRIVATE` (schemas/objects) keeps them usable internally while hiding
them from public HTTPS.

## See Also

- `mariadb-rest-service-create` — creating services, schemas, views, procedures and functions, and all field/CRUD annotations.
- `mariadb-rest-service-authorization` — auth apps, users, roles and REST privileges.
- `mariadb-alter-table`, `mariadb-create-view` — altering the underlying database objects.
