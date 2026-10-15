---
name: mariadb-schema-management-create
description: "Scaffold a MariaDB Schema Management (MSM) project and author the initial schema in the development folder — create the project with msm.create_project and write the first version's tables, objects and grants into the MSM sections of <schema>_next.sql. Use when starting a new versioned/maintainable MariaDB schema, creating an MSM schema project, or authoring the initial development script. Read mariadb-schema-management first for the section model."
---

# MSM — Creating the Initial Schema

This is step 1 of the MSM lifecycle (see `mariadb-schema-management` for the
overview and the full section model). Here you scaffold the project and author
the **first** version of the schema in the development folder. Driven by the
`msm.*` tools of the `mariadb-shell` MCP server. Assume MariaDB 11.8.

## 1. Scaffold the project

```text
msm.create_project(
    schema_name="notes-app",
    target_path="<parent dir>",
    copyright_holder="...",   # optional
    license="MIT",            # optional: GPL-2.0 | MIT | BSD | None
)
```

This creates `<schema>.msm.project/` with `msm.project.json`, the
`development/<schema>_next.sql` working script (initial development version
`0.0.1`), and the empty `releases/{versions,updates,deployment}/` folders.
`msm.get_project_information` returns the schema name, versions and paths.

Do **not** add the standalone "Start Block" from `mariadb-schema-create-script`
here — sections 010/920 already save and restore the server variables.

## 2. Author the schema into the right sections

Edit `development/<schema>_next.sql` by section, using
`msm.set_section_sql_content(file_path, section_id, sql_content)` (and
`msm.get_sql_content_from_section` to read one) so the section banners stay
intact. Put each kind of object in the section that matches how MSM deploys it:

- **Section 140 — tables and base data (non-idempotent).** `CREATE TABLE` and
  standard seed `INSERT`s only. This becomes a stored-procedure body in the
  deployment script, so write plain `;`-terminated statements with **no
  `DELIMITER`**.

  ```sql
  CREATE TABLE `notes-app`.`note`(
      `id` INT AUTO_INCREMENT PRIMARY KEY,
      `title` VARCHAR(255) NOT NULL,
      `body` MEDIUMTEXT
  );

  INSERT INTO `notes-app`.`note`(`title`) VALUES ('Welcome');
  ```

- **Section 150 — all other objects (idempotent).** VIEWs, PROCEDUREs,
  FUNCTIONs, TRIGGERs, EVENTs. This is emitted at top level with `DELIMITER %%`;
  every object must be safe to re-run, so use `CREATE OR REPLACE` or an explicit
  `DROP ... IF EXISTS` first.

  ```sql
  DELIMITER %%

  CREATE OR REPLACE SQL SECURITY INVOKER VIEW `notes-app`.`note_titles` AS
      SELECT `id`, `title` FROM `notes-app`.`note`%%

  DROP PROCEDURE IF EXISTS `notes-app`.`add_note`%%
  CREATE PROCEDURE `notes-app`.`add_note`(IN t VARCHAR(255))
  BEGIN
      INSERT INTO `notes-app`.`note`(`title`) VALUES (t);
  END%%

  DELIMITER ;
  ```

- **Section 170 — authorization.** `CREATE ROLE IF NOT EXISTS` and `GRANT`.
  Also a stored-procedure body → plain `;`-terminated statements, no
  `DELIMITER`. It runs in full on every deployment, upgrades included, so it
  must be re-runnable; create every role before granting to it — a `GRANT` to a
  missing role fails the deployment (error 1133).
- **Section 180 — optional REST endpoints** (see `mariadb-rest-service-create`).
  Runs in full on every deployment: use `CREATE OR REPLACE REST ...`. The server
  needs the REST metadata schema, and only MariaDB Shell (`msm.deploy_schema`)
  can run these statements.
- **Sections 130 / 190 — creation helpers.** Optional routines whose names must
  start `msm_`, defined in 130 and dropped in 190; use them for logic needed only
  while building the schema.

## 3. Set the initial version

The version lives in section 910 (the `msm_schema_version` view). Set it with:

```text
msm.set_development_version(version="0.1.0")
```

Use whatever development version you intend to release first; MSM starts a fresh
project at `0.0.1`.

## Guidelines

- Only tables/data go in 140; **everything else** goes in 150 — mixing them
  breaks the deployment script's create/upgrade split.
- Idempotent objects (150) must use `CREATE OR REPLACE` / `DROP IF EXISTS`.
- Keep object definitions grouped and commented; once the file grows, split
  sections into SOURCE breakout files (see `mariadb-schema-management-develop`).
- When the first version is ready, prepare a release
  (`mariadb-schema-management-release`).

## See Also

- `mariadb-schema-management` — lifecycle overview and full section model.
- `mariadb-schema-management-develop` — evolving the schema and SOURCE breakout files.
- `mariadb-schema-management-release` — preparing the first release.
- `mariadb-create-table`, `mariadb-create-view`, `mariadb-create-procedure`, `mariadb-create-function`, `mariadb-grant` — the underlying DDL.
