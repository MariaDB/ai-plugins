---
name: mariadb-schema-management-deploy
description: "Deploy a MariaDB Schema Management (MSM) schema version onto a live server with msm.deploy_schema — running the generated deployment script over an open db.connect connection to create the schema fresh or upgrade any prior released version to the target, optionally taking a backup first. Use when installing or upgrading an MSM-managed schema on a MariaDB server, applying a schema deployment/migration, or checking which versions are deployable. Read mariadb-schema-management first for the section model."
---

# MSM — Deploying a Schema Version

The final lifecycle step: apply a generated deployment script to a MariaDB
server. One script both **creates a fresh schema** and **upgrades any older
released version** to the target. Driven by `msm.*` + `db.*` tools of the
`mariadb-shell` MCP server. See `mariadb-schema-management` for the model.
Assume MariaDB 11.8.

## Prerequisite

The deployment script for the target version must already exist
(`releases/deployment/<schema>_deployment_<version>.sql`), i.e. the release was
prepared, its update script filled, and the deployment script generated — see
`mariadb-schema-management-release`. Check what is deployable with
`msm.get_deployment_script_versions`.

## Deploy

```text
1. conn = db.connect(uri="root@host:port")        # open a connection first
2. msm.deploy_schema(
       connection_id=conn,
       version="1.1.0",        # optional; defaults to the latest generated script
       backup=True,            # optional; dump an existing schema before upgrading
       backup_directory="...", # optional; where the backup is written
   )
```

`msm.deploy_schema` runs the deployment script on that connection. It requires an
open connection (that is why the tool is only available alongside the `db.*`
group). With `backup=True`, an existing schema is dumped first so a failed
upgrade can be restored.

## Create-or-upgrade semantics

The deployment script decides what to do from the target schema's state:

- **Empty / absent schema →** created fresh at the target version.
- **Existing MSM schema at an older released version →** upgraded by running each
  `msm_update_<from>_to_<to>()` in sequence up to the target, then applying the
  target's idempotent objects (150), authorization (the 270 steps, then 170) and
  REST endpoints (180).
- **Already at the target version →** nothing to change.

The `msm_schema_version` view is the source of truth for the installed version;
it is set to `0,0,0` while a create/upgrade is in progress. The script aborts
with a clear `SIGNAL` error when it cannot safely proceed:

- a non-MSM schema of the same name exists (no `msm_schema_version` view);
- the schema is stuck at `0,0,0` (a previous run failed or was interrupted;
  `msm.deploy_schema` reports that version `0.0.0` cannot be updated) — without
  `backup=True`, a failed upgrade leaves the schema in that state;
- the current version has no update path in this deployment script.

Inspect the project with `msm.get_last_released_version` /
`msm.get_released_versions` and `msm.get_deployment_script_versions` /
`msm.get_last_deployment_version` — all four read the project folder, not the
server. To see what a server has, query the view through the connection:
``db.execute_sql(connection_id=conn, sql="SELECT * FROM `<schema>`.`msm_schema_version`")``.

## Guidelines

- Deploy the **generated** script only; never a hand-edited deployment file.
- Use `backup=True` for production upgrades so a failure is recoverable.
- Upgrades are only possible along the released-version chain — if a server is on
  a version with no update script leading toward the target, the deployment will
  refuse it. Ensure every release was prepared with its update script filled.
- Re-running the same version is safe (idempotent objects re-create cleanly; the
  create/upgrade dispatcher is version-guarded).

## See Also

- `mariadb-schema-management` — lifecycle overview and full section model.
- `mariadb-schema-management-release` — generating the deployment script this step runs.
- `mariadb-schema-management-develop` — the development script releases are cut from.
