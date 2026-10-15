---
name: mariadb-rest-service-authorization
description: "Set up authentication and authorization for a MariaDB REST Service — create a REST AUTH APP (MRS, MYSQL or OAuth2 vendor), link it to a service, add REST users, and control access with REST roles and GRANT/REVOKE REST CREATE/READ/UPDATE/DELETE privileges at service/schema/object level. Use when asked to require login on REST endpoints, create auth apps or REST users, or manage REST roles and permissions on MariaDB."
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

`CONFIGURE REST METADATA` creates five MariaDB roles with the minimal privileges
each task needs. Grant them (in any combination) to the MariaDB accounts your
administrators and the REST Daemon use — never manage MRS as `root`.

| Role | Purpose |
| --- | --- |
| `mysql_rest_service_admin` | Full MRS admin: services, schemas, endpoints, auth apps, users, roles, content. |
| `mysql_rest_schema_admin` | Manage endpoint schemas and their endpoints/content. |
| `mysql_rest_service_dev` | Like schema admin but cannot add new schemas to a service. |
| `mysql_rest_service_data_provider` | The role the REST Daemon uses to run SQL for HTTP requests. Auto-granted the object privileges each endpoint needs. |
| `mysql_rest_service_meta_provider` | The role the REST Daemon uses to read MRS metadata. |

> These names are unchanged from the upstream MySQL REST Service. Schema
> admins/developers must themselves hold (with `GRANT OPTION`) the `SELECT` /
> `INSERT` / `UPDATE` / `DELETE` privileges on any object they expose, so
> `mariadb-shell` can re-grant them to `mysql_rest_service_data_provider`.

> All REST requests, whatever MRS user they come from, execute through the single
> `mysql_rest_service_data_provider` role. MRS enforces per-user access at the
> endpoint level, so be careful which views/procedures you expose.

## Step 1 — Require authentication on endpoints

Authentication is only enforced where you ask for it. A service, schema or object
requires login when `AUTHENTICATION REQUIRED` is set (objects default to
`AUTHENTICATION REQUIRED`; `AUTHENTICATION NOT REQUIRED` makes an endpoint
public). See `mariadb-rest-service-create` / `mariadb-rest-service-update-endpoints`.

```sql
ALTER REST VIEW /post ON SERVICE /myService SCHEMA /blog
    AUTHENTICATION REQUIRED;
```

## Step 2 — CREATE REST AUTH APP

An auth app defines *how* users prove identity. Pick a `VENDOR`:

| Vendor | Type | Use |
| --- | --- | --- |
| `MRS` | MRS | Built-in MRS accounts (SCRAM). Manage users with `CREATE REST USER`. |
| `MYSQL` | MariaDB server | Authenticate against MariaDB server accounts; best for tooling with fixed accounts over HTTPS. |
| `Facebook` | OAuth2 | "Login with Facebook". |
| `Google` | OAuth2 | "Login with Google". |
| `"OCI OAuth2"` | OAuth2 | OCI identity domain. |

```sql
-- Built-in MRS authentication
CREATE REST AUTH APP "MRS" VENDOR MRS;

-- MariaDB server-account authentication
CREATE REST AUTH APP "ServerAuth" VENDOR MYSQL;
```

Options (repeatable): `ENABLED`/`DISABLED`, `COMMENT`,
`[DO NOT] ALLOW NEW USERS [TO REGISTER]`, `DEFAULT ROLE <role>`, and — for OAuth2
vendors — `(APP|CLIENT) ID`, `(APP|CLIENT) SECRET` and `URL`. Setting a
`DEFAULT ROLE` gives every newly authenticated user a baseline role
automatically.

For OAuth2 you must register the application with the vendor first; the vendor
issues the `CLIENT ID` / `CLIENT SECRET`, and the vendor's authorization server
`URL` is required:

```sql
CREATE REST AUTH APP "OCI"
    VENDOR "OCI OAuth2"
    URL "https://idcs-....identity.oraclecloud.com:443"
    CLIENT ID "f2abc2c0f19a4c40a1abc48edcdfe60b"
    CLIENT SECRET "**********************";
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

Manage them with `ALTER REST USER "alice"@"MRS" IDENTIFIED BY "..."` (also
`ACCOUNT LOCK`/`UNLOCK`, `APP OPTIONS`) and `DROP REST USER`. OAuth2 and `MYSQL`
vendors don't need `CREATE REST USER` — identities come from the vendor / server.

## Step 5 — Authorize with roles and privileges

A **REST role** bundles REST privileges you can grant to users. Privileges are
`CREATE`, `READ`, `UPDATE`, `DELETE` and can be granted at three levels; access
cascades downward (schema access implies access to its objects):

- **Service** — `ON SERVICE /svc` (or `ON SERVICE /svc/*` wildcard)
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
SHOW REST ROLES ON SERVICE /myService;
SHOW REST ROLES FOR "ulf"@"TestAuthApp";
SHOW REST GRANTS FOR "reader" ON SERVICE /myService;
SHOW CREATE REST AUTH APP "TestAuthApp" FROM SERVICE /myService;
SHOW CREATE REST ROLE "editor" ON SERVICE /myService;
SHOW CREATE REST USER "ulf"@"TestAuthApp";
```

## See Also

- `mariadb-rest-service-create` — creating the service/schema/objects these roles protect, and the `@ROWOWNERSHIP` annotation.
- `mariadb-rest-service-update-endpoints` — toggling `AUTHENTICATION REQUIRED`, adding/removing auth apps, altering users.
- `mariadb-grant`, `mariadb-create-user` — the MariaDB server privileges and accounts behind the administrative roles.
