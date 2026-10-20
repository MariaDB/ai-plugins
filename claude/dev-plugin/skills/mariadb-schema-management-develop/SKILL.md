---
name: mariadb-schema-management-develop
description: "Develop the next version of a MariaDB Schema Management (MSM) schema in development/<schema>_next.sql, and keep large scripts maintainable by breaking section bodies out into development/sections/ files linked with the SOURCE '<path>'[start:end]; statement. Use when evolving an existing MSM schema for a new version, editing the _next.sql development script, or splitting a growing schema script into SOURCE-included section files. Read mariadb-schema-management first for the section model."
---

# MSM — Developing the Next Version

After a release, `prepare_release` has already bumped the development version and
you continue editing `development/<schema>_next.sql` toward the next release.
This skill covers iterating on that script and the **SOURCE breakout** mechanism
for keeping it maintainable. See `mariadb-schema-management` for the section
model. Assume MariaDB 11.8.

## Iterating on `_next.sql`

Make changes in the same sections you authored initially, using
`msm.set_section_sql_content` / `msm.get_sql_content_from_section`:

- New/changed **tables and data** → section 140.
- New/changed **views, routines, triggers, events** → section 150 (idempotent:
  `CREATE OR REPLACE` / `DROP IF EXISTS`). This is the ONLY place for them: the
  target's section 150 runs in full on every deployment, so upgraded schemas
  get them too. Removing an object additionally needs a `DROP ... IF EXISTS` in
  the update script's section 240.
- **Grants/roles** → section 170 (`CREATE ROLE IF NOT EXISTS`, then `GRANT`);
  it also runs on every deployment. Revoking a privilege additionally needs a
  `REVOKE` in the update script's section 270.

The development file always describes the **full, current** schema (not a diff) —
it is the source for the next version snapshot. The per-release *migration* from
the previous version is written separately when you prepare the release (see
`mariadb-schema-management-release`, sections 240/270).

Keep the development version in section 910 current with
`msm.set_development_version` as the target version firms up.

## SOURCE breakout files (keeping the script maintainable)

When a section grows large, move its body into one or more files under
`development/sections/` and reference them from `_next.sql` with a `SOURCE`
statement. MSM inlines this content when it snapshots the version during
`prepare_release`, so SOURCE is purely a **development-time** organizing tool —
released version and deployment scripts are always fully inlined.

### Syntax

```sql
SOURCE '<relative-or-absolute-path>'[<start>:<end>]; -- optional comment
```

- The `[start:end]` slice is optional and selects the part of the referenced
  file to inline; without it (or with `[:]`) the whole file is inlined. Each
  bound is empty, a **line number** `lnN`, or a **character offset**, and the two
  kinds mix freely:
  - `[ln4:]` — from line 4 on (drop a three-line copyright header).
  - `[ln4:ln-4]` — lines 4 through the 4th-last (drop the last three too).
    Lines count from 1, the end line is included, `ln-1` is the last line.
  - `[53:]` — drop the first 53 characters (Python slice; negative counts from
    the end, so `[663:-115]` also drops a 115-character footer).
- Line numbers and the optional slice need a MariaDB Shell newer than 26.10.2
  (its `msm_plugin` with mariadb-shell-plugins PR #60). With 26.10.2 or older,
  always give a slice of character offsets: there a `SOURCE` line without a
  slice is copied into the release verbatim and fails the deployment, and `[:]`
  makes `prepare_release` fail.
- Relative paths resolve against the **development/** folder (where `_next.sql`
  lives), so use `'./sections/...'`.
- The leading indentation of the `SOURCE` line is applied to every inlined line.

### Why the slice

Each breakout file is a **standalone, valid SQL file** with its own copyright
header (and optionally a footer). The slice strips that header/footer so only the
object definitions are inlined into `_next.sql`. Prefer line numbers: `[ln4:]`
stays right when the header's text changes but not its line count, while a
character offset must be recounted whenever the header is edited.

### Example

`development/<schema>_next.sql`, section 140 body:

```sql
SOURCE './sections/140-10_tables.sql'[663:-115]; -- Ignore header and footer
SOURCE './sections/140-30_inserts.sql'[53:];     -- Remove copyright header
```

section 150 body:

```sql
SOURCE './sections/150-10_views.sql'[53:];
SOURCE './sections/150-20_procedures_functions.sql'[53:];
SOURCE './sections/150-30_triggers.sql'[53:];
```

### File naming convention

Name breakout files `<section-id>-<NN>_<topic>.sql` so they sort in load order
and map back to their section, e.g. `140-10_tables.sql`,
`140-30_inserts.sql`, `150-20_procedures_functions.sql`, `170_roles.sql`.

### Rules

- Respect the section's placement/delimiter rule even in breakout files: content
  destined for 140/170 must be plain `;`-terminated (it lands in a
  stored-procedure body); content for 150 uses `DELIMITER %%` for routine bodies.
- Keep the `SOURCE` lines inside the correct MSM section of `_next.sql`; edit that
  section body via `msm.set_section_sql_content` so the banners stay intact.
- After editing breakout files, a `prepare_release` will inline them; verify the
  generated version snapshot looks complete.

## Next

When the development version is feature-complete, prepare a release:
`mariadb-schema-management-release`.

## See Also

- `mariadb-schema-management` — lifecycle overview and full section model.
- `mariadb-schema-management-create` — the initial project + first authoring.
- `mariadb-schema-management-release` — snapshot the version and write the migration.
- `mariadb-alter-table`, `mariadb-create-view`, `mariadb-create-procedure` — the DDL you edit here.
