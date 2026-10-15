---
name: mariadb-migrator-verify
description: "Verify a finished MySQL-to-MariaDB migration on the target with the db.* tools and report it — object counts per type, foreign keys, row counts and value spot-checks (never a checksum unless asked), authenticating as each migrated account, the four things that vanish silently through MySQL's /*!80016*/ version gates (CHECK NOT ENFORCED, SRID, DEFAULT ENCRYPTION, utf8mb4_0900 collations), and the fixed markdown comparison table — one per database, real pipes, nothing added when every check comes back clean. Use when a migration run has finished and its result has to be checked or reported, or when asked whether a migration really succeeded. Read mariadb-migrator first for the tools and preconditions."
---

# Migration — Verify on the Target, Then Report

Do not report a migration as successful on the tooling's exit code alone. This
step assumes a run that actually loaded data onto a target; a mode 3
`dump_only` phase is verified and reported differently — see
`mariadb-migrator-modes`.

## Verify with the `db.*` tools

Open the target with `db.connect` and confirm what arrived:

- `db.list_schemas` — the migrated schemas are present.
- `db.list_objects(schema_name=..., object_type=...)` for `table`, `view`,
  `trigger`, `procedure`, `function`, `event` — every object type the dump
  carries, not just the tables.
- `db.get_object_details` — foreign keys survived (the constraint name is inside
  `reference_mapping["constraint"]`, as `<schema>.<name>`).
- `db.execute_sql` — row counts per table, and spot-check a handful of real
  values. **Row counts and value spot-checks are the default verification —
  never run a checksum unless the operator explicitly asks for one.** A
  full `CRC32`/`BIT_XOR` checksum, even over a sample, is extra query load
  that isn't part of the default report and shouldn't run just because a
  table happens to be small — "cheap" is still slower than not running it
  at all, and the default path should be fast every time, not fast most of
  the time.

  If the operator does ask for a checksum, run it the same deterministic
  way every time so results are comparable across runs: order by primary
  key, checksum a **fixed sample** (e.g. every Nth row by primary key, or
  the first/last N rows) — never an unseeded `RAND()` sample, which can't be
  reproduced or compared. State the sample method used alongside the result
  so a mismatch is actionable rather than a mystery.
- **Authenticate as each migrated account.** A row in `mysql.user` is not a
  working login; see the `MIGRATE_APP_USERS` notes in
  `mariadb-migrator-configure` for why.

## The things that vanish without any error

Everything in that list catches loud failures. MySQL dumps wrap newer features
in `/*!80016 ... */` version gates, which are **executable version-gated SQL, not
comments** — MariaDB skips them and raises nothing. Three features disappear
this way, invisibly, on a run that reports every step `DONE`:

- `CHECK ... NOT ENFORCED` constraints — MDEV-28906 excludes these as won't-fix
- SRID enforcement on spatial columns — MDEV-29953
- `DEFAULT ENCRYPTION` clauses

If the source uses any of them, check the target definitions by hand. **When
reporting an actual finding, keep it to one short line: what was lost, on
which object, and the fix — not a technical narrative.** "SRID enforcement
was dropped on `sakila_mig_copy.address.location`; re-add it with `ALTER
TABLE ... MODIFY location geometry ... REF_SYSTEM_ID=0` if you want it back"
is enough. Skip the gate syntax (`/*!80003 ... */`), the MDEV bug number, and
an explanation of *why* MariaDB skips it — that detail exists in this skill
file already and isn't needed to act on the finding. Offer it only if asked.
A clean report is not evidence here, but a real finding still doesn't need
paragraphs to be actionable.

**Collation is a fourth, quieter one.** MariaDB 11.8 accepts the
`utf8mb4_0900_*` family as compatibility aliases for its UCA 14.0.0 collations
(MDEV-35256), so these columns migrate without complaint — but MySQL's `_0900_`
collations are Unicode 9.0, and characters whose weights changed between 9.0 and
14.0 can sort and compare differently. Only flag this when there's a real
consequence: a unique index on a `_0900_`-collated text column. When you do,
one line is enough — name the column and say a duplicate-key or near-duplicate
risk exists — not the Unicode-version explanation above; that stays in this
file for Claude's own reference, not the operator's report.

## Report the result

Once the checks above are done, report the outcome without waiting to be
asked — lead with one line ("Verified on the target rather than from the
exit code:"), then an actual **markdown table** comparing source and
target side by side, using real pipe characters and a `| --- | --- | --- |`
header separator so it renders as a table rather than plain lines:

| Check | Source | Target |
| --- | --- | --- |
| Base tables | *count* | *count* |
| Views | *count* | *count* |
| Triggers | *count* | *count* |
| Procedures / functions / events | *count / count / count* | *count / count / count* |
| Foreign keys | *count* | *count* |
| Row counts (all *N* tables) | — | `identical` if every table matched, otherwise show which didn't |
| *one representative spot-check* (e.g. the largest BLOB/LOB column, a geometry value) | the value or hash | the value or hash |

Fixed rows, always in that order, so the shape is the same every run — fill
in the numbers, don't restructure it per migration. The spot-check row
shows one concrete comparable value (a hash or literal), not a "ran/passed"
count — that's what makes it a comparison table rather than a checklist.
Close with the artifacts path on its own line (`Run artifacts: <install_dir>/<out_dir>`).

**This has broken before, so check it explicitly before sending.** This is
wrong, even though it contains the same information:

```
Check: Base tables
Source: 18
Target: 18
────────────────────────
Check: Views
Source: 7
Target: 7
```

That is a "Check: X / Source: Y / Target: Z" text block, not a table — it
does not have `|` pipe characters or a `| --- | --- | --- |` separator row,
so it will not render as a table no matter how consistently formatted it
looks. Before finishing the response, re-read what you're about to send
and confirm it literally contains a `| --- | --- | --- |` line — if it
doesn't, it is not the format this step requires, regardless of which mode
or phase produced the result (`dump_and_load`, `two_step`, `load_only`,
anything that touched a target).

**This table assumes a run that actually loaded data onto a target** —
`dump_and_load`, `load_only`, or any non-staged mode all qualify, so it
applies to them without exception. **Only a `dump_only` phase skips this
table** — use the dump-verification report described in
`mariadb-migrator-modes` instead (manifest check, per-database file sizes,
elapsed time, and the `STAGED_DUMP_DIR` hand-off line), since there's no
target yet to compare against.

### One table per database

**When `SRC_DBS` names more than one database, render one table per
database, not one merged table.** A combined count (e.g. "32 base tables"
across two schemas) hides which schema actually has what, and can't
represent a per-schema mismatch if only one of them drifts. Give each
database its own small heading and its own table with the same fixed rows:

**`sakila_mig_copy`**

| Check | Source | Target |
| --- | --- | --- |
| Base tables | *count* | *count* |
| … | | |

**`airportdb`**

| Check | Source | Target |
| --- | --- | --- |
| Base tables | *count* | *count* |
| … | | |

The spot-check row can stay a single shared row across all databases, or
one per database if the notable object lives in a specific one — pick
whichever is clearer, but don't duplicate the same value under both. The
artifacts line stays singular at the very end, after every database's
table, since one run produces one artifacts directory regardless of how
many schemas it touched.

**Every table gets its own complete header row and border — never carry
over or abbreviate the second table's structure because the first one
already showed the shape.** Each database's table is a fresh, independent
`| Check | Source | Target |` block with its own `| --- | --- | --- |`
separator and every cell filled in; don't drop the header, merge cells
across rows, or let a later table's columns come out narrower or missing
values just because the pattern was already established once above.

### What does not go in the report

Silent-loss findings are not a row in this table — report them as short
prose immediately after it, and **only when a check actually turned
something up.** "I checked CHECK constraints, SRID enforcement, DEFAULT
ENCRYPTION, and collation, and none of them applied" is not a finding, it's
a narration of the checking process — that belongs in this same "stop
there" rule, not an exception to it. If every one of the four risks above
comes back clean, say nothing about them at all; don't list the risks you
ruled out as if ruling something out were itself news. If nothing
was found, that table plus the artifacts line is the **entire** report —
stop there. Don't follow a clean table with a prose paragraph re-explaining
rows that already matched, and don't follow it with a paragraph explaining
which checks you ran and cleared either; both are the same over-reporting
instinct and both are where output tends to get long and garbled.
Per-table row counts and full finding detail still exist — surface them
only if something in the table doesn't match, or the operator asks to see
more.

**Preflight or setup noise that didn't cause a failure isn't part of the
report.** If a known-defect gate fires but the run still succeeded (e.g. the
over-eager MySQL 8.4+ `mysqldump` gate listed in
`mariadb-migrator-troubleshooting`, which is diagnostic only for mode
4/binlog-adjacent checks and doesn't affect modes 1–3), it's already covered
as a known defect — don't relay it to the operator as a run note. Report what
changed the outcome, not everything the tooling logged along the way.

## See Also

- `mariadb-migrator` — the overview: tools, preconditions, modes at a glance.
- `mariadb-migrator-run` — the run whose report this checks, and the baseline to hold.
- `mariadb-migrator-modes` — the `dump_only` variant of this report.
- `mariadb-migrator-configure` — the `MIGRATE_APP_USERS` account caveats.
- `mysql-to-mariadb` — MySQL/MariaDB dialect and feature differences, for fixing
  up SQL that the migration carried across verbatim.
