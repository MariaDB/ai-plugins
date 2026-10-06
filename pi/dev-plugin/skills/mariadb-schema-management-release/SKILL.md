---
name: mariadb-schema-management-release
description: "Prepare a MariaDB Schema Management (MSM) version release — snapshot the development script with msm.prepare_release, FILL the generated previous→new update script (table changes and drops in section 240, revoked privileges in 270) with the actual migration, and only then generate the deployment script with msm.generate_deployment_script. Use when cutting/preparing an MSM schema release or version, writing the release-to-release migration, or generating a deployment script. Read mariadb-schema-management first for the section model."
---

# MSM — Preparing a Version Release

This step turns the current development script into a released version and, for
any release after the first, produces the migration from the previous release.
See `mariadb-schema-management` for the section model. Assume MariaDB 11.8.

**The order is mandatory:**

```text
1. msm.prepare_release          → version snapshot (+ empty update script)
2. FILL the update script       → sections 240 (+ 270)  ← do NOT skip
3. msm.generate_deployment_script  ← only after step 2
```

## 1. Prepare the release

```text
msm.prepare_release(version="1.1.0", next_version="1.2.0")
```

This:
- Inlines any `SOURCE` breakout files and writes the full snapshot
  `releases/versions/<schema>_1.1.0.sql`.
- If a previous release exists, creates an **empty** update script
  `releases/updates/<schema>_<prev>_to_1.1.0.sql` from the template.
- Bumps the development version in `_next.sql` to `next_version` (1.2.0).

Semver validation: `version` must be ≥ the last released version, and
`next_version` must be greater than `version` (unless
`allow_to_stay_on_same_version` is set). The **first** release has no update
script.

## 2. FILL the update script — the step everyone forgets

`prepare_release` only creates the update script; it does **not** know how to
migrate data/structure. You must write the migration from the previous release
to this one into its sections, using `msm.set_section_sql_content(file_path,
section_id, sql_content)`:

- **Section 240 — non-idempotent changes + all drops.** `ALTER TABLE`, new
  `CREATE TABLE`, data backfill (`UPDATE`/`INSERT`), and any `DROP` of objects
  that would block a table change. Order matters — these are largely
  irreversible. This becomes a stored-procedure body in the deployment script, so
  write plain `;`-terminated statements, **no `DELIMITER`**; use dynamic SQL
  (`PREPARE`/`EXECUTE`) for conditional DDL.

  ```sql
  ALTER TABLE `notes-app`.`note` ADD COLUMN `created_at` DATETIME;
  UPDATE `notes-app`.`note` SET `created_at` = NOW() WHERE `created_at` IS NULL;
  ```

- **Section 250 — leave it empty; it is not deployed.** New and changed VIEWs /
  routines / triggers / events belong in the dev script's section 150. The
  deployment script runs the target version's full section 150 on every
  deployment, after all table changes, so they reach upgraded schemas without
  any per-version statement. A *removed* object is the one change 150 cannot
  express — drop it in 240 with `DROP ... IF EXISTS`.
- **Section 270 — revoked privileges and dropped roles only.** `REVOKE` /
  `DROP ROLE` for what the new version no longer has (stored-procedure body →
  plain `;`, no `DELIMITER`). New roles and `GRANT`s belong in the dev script's
  section 170, which also runs on every deployment, after the 270 steps.
  **Never `GRANT` in 270**: on an upgrade it runs before 170 creates a role that
  is new in this version, and the deployment fails with error 1133.
- **Sections 230 / 290 — update helpers** (`msm_`-prefixed) if the migration
  needs temporary routines; drop them in 290.

Write the migration to match exactly what changed in the **tables** between the
previous version snapshot and this one: an upgraded schema must end with the
same tables as a fresh install of the new version. If a section has no changes,
leave it empty.

## 3. Generate the deployment script

Only after the update script is filled:

```text
msm.generate_deployment_script(version="1.1.0")
    → releases/deployment/<schema>_deployment_1.1.0.sql
```

What it produces:
- For the **first** release, the deployment script is just the version snapshot.
- Otherwise it is a self-contained script that **either creates fresh or upgrades
  any prior released version** to the target: it builds `msm_create_<target>()`
  from section 140, an `msm_update_<from>_to_<to>()` from **each** update script's
  section 240, an `msm_create_or_update()` dispatcher that reads
  `msm_schema_version` and applies the right path, then the target's idempotent
  objects (150), authorization (`msm_auth_*`: the 270 steps, then the target's
  170) and REST endpoints (180), and finally drops all `msm_` procedures and
  stamps the new version. The update scripts' section 250 is not included.

Because it embeds the update sections, generating **before** filling them yields
a script that can create fresh but cannot correctly upgrade older installs. Every
gap between consecutive released versions needs a filled update script for the
upgrade chain to be complete.

Deployment scripts are **generated artifacts** — never hand-edit; re-generate.

## Next

Deploy the release onto a server: `mariadb-schema-management-deploy`.

## See Also

- `mariadb-schema-management` — lifecycle overview and full section model.
- `mariadb-schema-management-develop` — the development script the snapshot comes from.
- `mariadb-schema-management-deploy` — running the deployment script on a server.
- `mariadb-alter-table` — the DDL for section 240.
- `mariadb-grant` — new grants, in the dev script's section 170; `mariadb-revoke` — revoked privileges, in section 270.
