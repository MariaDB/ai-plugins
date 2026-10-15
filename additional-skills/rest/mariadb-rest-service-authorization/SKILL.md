---
name: mariadb-rest-service-authorization
description: "Set up authentication and authorization for a MariaDB REST Service — create a REST AUTH APP (MRS, MARIADB or OAuth2 vendor), link it to a service, add REST users, and control access with REST roles and GRANT/REVOKE REST CREATE/READ/UPDATE/DELETE privileges at service/schema/object level. Use when asked to require login on REST endpoints, create auth apps or REST users, or manage REST roles and permissions on MariaDB."
---

# MariaDB REST Service Authentication & Authorization

The MariaDB REST Service performs its **own** HTTP authentication and
authorization, separate from MariaDB server accounts. To let clients access
protected endpoints you: create a **REST authentication app** (a vendor-backed
login mechanism), **link it to a REST service**, add **REST users** (for the
built-in MRS vendor), and grant access with **REST roles** and **REST
privileges**. All of this is DDL run in **`mariadb-shell`**.

Assume MariaDB 11.8 if not told otherwise.

## Two layers: administration vs. end-user access

Do not confuse them:

- **Administrative access** (who may run this DDL) is governed by MariaDB server
  roles granted to the account `mariadb-shell` connects with — see
  *Administrative roles* below.
- **End-user access** (who may call an endpoint over HTTP) is governed by REST
  auth apps, REST users and REST roles — the bulk of this skill.

## Administrative roles

`CONFIGURE REST METADATA` creates six MariaDB roles with the minimal privileges
each task needs. Grant them to the MariaDB accounts your administrators, the
REST Daemon and server-account REST users use — never manage MRS as `root`.

| Role | Purpose |
| --- | --- |
| `mariadb_rest_service_admin` | Full MRS admin: services, schemas, endpoints, auth apps, users, roles, content, REST Daemons. |
| `mariadb_rest_service_schema_admin` | Add REST schemas to existing services, and manage their endpoints/content. |
| `mariadb_rest_service_dev` | Like schema admin but cannot add new schemas to a service. |
| `mariadb_rest_service_user` | For MariaDB accounts that call endpoints through the `MARIADB` vendor (below). |
| `mariadb_rest_service_data_provider` | The role the REST Daemon uses to run SQL for HTTP requests. Auto-granted the object privileges each endpoint needs. |
| `mariadb_rest_service_meta_provider` | The role the REST Daemon uses to read MRS metadata. |

A metadata schema created with a prefix/postfix (`CONFIGURE REST METADATA SCHEMA
acme_mariadb_rest_service`) has its own roles with the same affixes, e.g.
`acme_mariadb_rest_service_admin`.

MariaDB activates one role per session, and REST SQL only sees a role that is
active, so make it the account's **default role** (to combine roles, grant them
to a role of your own and make that the default):

```sql
GRANT mariadb_rest_service_admin TO 'dba'@'%';
SET DEFAULT ROLE mariadb_rest_service_admin FOR 'dba'@'%';
```

> Schema admins/developers must themselves hold (with `GRANT OPTION`) the
> `SELECT` / `INSERT` / `UPDATE` / `DELETE` privileges on any object they expose,
> so `mariadb-shell` can re-grant them to `mariadb_rest_service_data_provider`.

> All REST requests of `MRS` and OAuth2 users execute through the single
> `mariadb_rest_service_data_provider` role (only `MARIADB`-vendor users run with
> their own privileges). MRS enforces per-user access at the endpoint level, so be
> careful which views/procedures you expose.

## Step 1 — Require authentication on endpoints

Authentication is only enforced where you ask for it. A REST schema, object or
content set requires login when `AUTHENTICATION REQUIRED` is set (REST
views/procedures/functions default to `AUTHENTICATION REQUIRED`, REST schemas to
`NOT REQUIRED`; `AUTHENTICATION NOT REQUIRED` makes an endpoint public). See
`mariadb-rest-service-create` / `mariadb-rest-service-update-endpoints`.

```sql
ALTER REST VIEW /post ON SERVICE /myService SCHEMA /blog
    AUTHENTICATION REQUIRED;
```

## Step 2 — CREATE REST AUTH APP

An auth app defines *how* users prove identity. Pick a `VENDOR`
(`SHOW REST AUTH VENDORS` lists the vendors the metadata knows):

| Vendor | Type | Use |
| --- | --- | --- |
| `MRS` | MRS | Built-in MRS accounts (SCRAM). Manage users with `CREATE REST USER`. |
| `MARIADB` | MariaDB server | Vendor "MariaDB Internal": authenticate against MariaDB server accounts, which need the `mariadb_rest_service_user` role and access data with their own privileges. Passwords travel in clear text in the request body, so HTTPS only; best for tooling with fixed accounts. |
| `Facebook` | OAuth2 | "Login with Facebook". |
| `Google` | OAuth2 | "Login with Google". |

There is no `MYSQL` vendor. Configuring the metadata already creates an auth app
named `MariaDB` with the `MARIADB` vendor, ready to link to a service.

```sql
-- Built-in MRS authentication
CREATE REST AUTH APP "MRS" VENDOR MRS;

-- MariaDB server-account authentication
CREATE REST AUTH APP "ServerAuth" VENDOR MARIADB;
```

Options (repeatable): `ENABLED`/`DISABLED`, `COMMENT`,
`[DO NOT] ALLOW NEW USERS [TO REGISTER]`, `DEFAULT ROLE <role>`, and — for OAuth2
vendors — `(APP|CLIENT) ID`, `(APP|CLIENT) SECRET` and `URL`.

`DEFAULT ROLE` is the role a newly authenticated (self-registered or first-time
OAuth2) user gets automatically. It must be a global role (`CREATE REST ROLE ...
ON ANY SERVICE`). **Without it, the default role is the built-in `Full Access`
role (CRUD on every endpoint)** — when new users may register, set a restrictive
global default role. Users you add with `CREATE REST USER` only get the roles you
grant them.

For OAuth2 you must register the application with the vendor first; the vendor
issues the `CLIENT ID` / `CLIENT SECRET`. `URL` (the vendor's OAuth2 server),
`CLIENT ID` and `CLIENT SECRET` are all required:

```sql
CREATE REST AUTH APP "Google"
    VENDOR Google
    URL "<url of the OAuth2 server>"
    CLIENT ID "<client id>"
    CLIENT SECRET "<client secret>";
```

For OAuth2 also set the service's redirection/validation via `AUTHENTICATION
REDIRECTION`/`VALIDATION` and register a redirect URL of the form
`https://<router-address>/<service>/authentication/login?authApp=<name>&sessionType=<bearer|cookie>`
with the vendor.

## Step 3 — Link the auth app to a service

An auth app must be linked to each service that uses it. Link with `ADD AUTH
APP` (on `CREATE`/`ALTER REST SERVICE`):

```sql
CREATE REST AUTH APP "MRS" VENDOR MRS;
ALTER REST SERVICE /myService ADD AUTH APP "MRS";

-- Remove a link later
ALTER REST SERVICE /myService REMOVE AUTH APP "MRS" IF EXISTS;
```

Once linked, the auth workflow is served under the service's authentication path
(default `/authentication`): `/login`, `/status`, `/logout`, `/completed`.

## Step 4 — Add REST users (MRS vendor)

For the built-in `MRS` vendor, create users against the auth app with
`user@authApp`:

```sql
CREATE REST USER "alice"@"MRS" IDENTIFIED BY "********";
CREATE REST USER "bob"@"MRS" IDENTIFIED BY "********" ACCOUNT UNLOCK;
```

Passwords must have at least 8 characters with an uppercase and a lowercase
letter, a digit and a special character, or the statement fails.

Manage them with `ALTER REST USER "alice"@"MRS" IDENTIFIED BY "..."` (also
`ACCOUNT LOCK`/`UNLOCK`, `APP OPTIONS`) and `DROP REST USER`. OAuth2 and `MARIADB`
vendors don't need `CREATE REST USER` — identities come from the vendor / server.

## Step 5 — Authorize with roles and privileges

A **REST role** bundles REST privileges you can grant to users. Privileges are
`CREATE`, `READ`, `UPDATE`, `DELETE` and can be granted at three levels; access
cascades downward (schema access implies access to its objects):

- **Service** — `ON SERVICE /svc` (paths may use the wildcards `*` and `?`,
  back-tick quoted: ``ON SERVICE `/svc*` ``)
- **Schema** — `ON SERVICE /svc SCHEMA /sch`
- **Object** — `ON SERVICE /svc SCHEMA /sch OBJECT /obj`

```sql
GRANT REST READ ON SERVICE /myService SCHEMA /blog OBJECT /post TO "reader";
GRANT REST CREATE, UPDATE ON SERVICE /myService SCHEMA /blog OBJECT /post TO "poster";
REVOKE REST DELETE ON SERVICE /myService SCHEMA /blog OBJECT /post FROM "poster";
```

Roles belong to a service by default (create in the current service or name it
with `ON SERVICE /svc`); role names are unique within a service. Use `ON ANY
SERVICE` for a role usable from every service, and `EXTENDS` to inherit another
role's privileges:

```sql
CREATE REST ROLE "reader";
CREATE REST ROLE "poster" EXTENDS "reader";
CREATE REST ROLE "globalRole" ON ANY SERVICE;
CREATE REST ROLE "myrole" ON SERVICE /myOtherService;
```

Grant a role to a user, and revoke it, with `user@authApp`:

```sql
GRANT REST ROLE "reader" TO "alice"@"MRS";
REVOKE REST ROLE "reader" FROM "alice"@"MRS";
```

### Built-in authorization models

If your use case fits one of these, you don't need custom authorization logic:

- **User-ownership based** — users see only their own rows (mark the owning
  column with the `@ROWOWNERSHIP` field annotation on the REST view).
- **Privilege based**, managed with roles (above).
- **User-hierarchy**, **group**, and **group-hierarchy** based.

## End-to-end example

```sql
-- Underlying database schema and table
CREATE SCHEMA IF NOT EXISTS blog;
CREATE TABLE IF NOT EXISTS blog.post(id INT PRIMARY KEY AUTO_INCREMENT, message TEXT);

CREATE REST SERVICE /myService;
USE REST SERVICE /myService;

CREATE REST SCHEMA /blog FROM blog;
CREATE REST VIEW /post ON SCHEMA /blog AS blog.post AUTHENTICATION REQUIRED;

-- Roles, layered with EXTENDS
CREATE REST ROLE "reader";
GRANT REST READ ON SERVICE /myService SCHEMA /blog OBJECT /post TO "reader";

CREATE REST ROLE "poster" EXTENDS "reader";
GRANT REST CREATE, UPDATE ON SERVICE /myService SCHEMA /blog OBJECT /post TO "poster";

CREATE REST ROLE "editor" EXTENDS "poster";
GRANT REST DELETE ON SERVICE /myService SCHEMA /blog OBJECT /post TO "editor";

-- Auth app + users, each with a role
CREATE REST AUTH APP "TestAuthApp" VENDOR MRS;
ALTER REST SERVICE /myService ADD AUTH APP "TestAuthApp";

CREATE REST USER "ulf"@"TestAuthApp" IDENTIFIED BY "********";
GRANT REST ROLE "reader" TO "ulf"@"TestAuthApp";

CREATE REST USER "mike"@"TestAuthApp" IDENTIFIED BY "********";
GRANT REST ROLE "editor" TO "mike"@"TestAuthApp";
```

## Inspect authorization

```sql
SHOW REST AUTH APPS FROM SERVICE /myService;
SHOW REST AUTH VENDORS;
SHOW REST USERS ON SERVICE /myService;
SHOW REST ROLES ON SERVICE /myService;
SHOW REST ROLES FOR "ulf"@"TestAuthApp";
SHOW REST GRANTS FOR "reader" ON SERVICE /myService;
SHOW CREATE REST AUTH APP "TestAuthApp";
SHOW CREATE REST ROLE "editor" ON SERVICE /myService;
SHOW CREATE REST USER "ulf"@"TestAuthApp";
```

## See Also

- `mariadb-rest-service-create` — creating the service/schema/objects these roles protect, and the `@ROWOWNERSHIP` annotation.
- `mariadb-rest-service-update-endpoints` — toggling `AUTHENTICATION REQUIRED`, adding/removing auth apps, altering users.
- `mariadb-grant`, `mariadb-create-user` — the MariaDB server privileges and accounts behind the administrative roles.
