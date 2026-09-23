---
order: 5
slug: diagnose-a-slow-query
title: "Diagnose a slow query with EXPLAIN"
description: >-
  Give the agent a query and a real server, and have it read the plan instead of
  guessing at indexes. Covers EXPLAIN, ANALYZE, the optimizer trace, and testing
  a candidate index on a sandbox before it reaches production.
level: intermediate
duration: "30 min"
area: performance
tools: ["db.connect", "db.execute_sql", "db.get_object_details", "sandbox.deploy"]
skills: ["mariadb-explain", "mariadb-query-optimization", "mariadb-create-index"]
path_label: "Operate and Optimize, Step 3"
prerequisites:
  - "[Tutorial 3](../browse-schema-objects/) — the agent needs to be able to read the schema."
  - "A connection to a server with enough data that a plan difference is measurable. A seeded sandbox works."
---

"Why is this query slow" is the request an agent most often answers badly,
because the honest answer requires looking at a plan, a schema and some
cardinalities — and a model with none of those will confidently suggest an
index. With the MCP server connected it does not have to guess.

<div class="prompt" markdown="1">
*This query takes four seconds. Connect to the sandbox, look at the actual plan
and the table definitions, and tell me why — then propose a fix and prove it
helps.*

```sql
SELECT u.display_name, COUNT(*) AS notes
FROM notes_app.note n
JOIN notes_app.`user` u ON u.id = n.user_id
WHERE n.created_at >= '2026-01-01'
  AND n.notebook_id = ?
GROUP BY u.id, u.display_name
ORDER BY notes DESC
LIMIT 20;
```
</div>

## Read the schema first

Insist on the table definitions before any plan is discussed — *"show me the
definitions of `note` and `user` first"*. Half of all slow-query answers are
visible in the DDL, and an index suggested without reading it is a guess:

- Is there an index on `notebook_id`? On `created_at`? On **both**, in an order
  that serves this predicate?
- Is `note.user_id` the same type and collation as `user.id`? A join across
  mismatched types cannot use the index on either side, and nothing in the plan
  says "type mismatch" — it just says `ALL`.
- Is `user.id` actually the primary key, or is the real primary key something
  else with a `UNIQUE` on `id`?

## `EXPLAIN` — what the optimizer intends

<div class="prompt" markdown="1">
*Show me `EXPLAIN` for that query, and then `EXPLAIN FORMAT=JSON` — I want the
filtering percentages, not just the table.*
</div>

`EXPLAIN` is an estimate, produced without running anything. The `mariadb-explain`
skill teaches the agent what the columns mean in MariaDB specifically. The
signals that matter most:

| What you see | What it means |
| --- | --- |
| `type: ALL` | Full table scan. On the *driving* table with a selective `WHERE`, this is the problem. |
| `type: index` | Full index scan — better than `ALL`, still every row. |
| `type: ref` / `eq_ref` / `const` | Index lookup. What you want. |
| `key: NULL` with candidate keys listed | An index exists and the optimizer declined it. Usually poor statistics or a non-sargable predicate. |
| `Extra: Using filesort` | Sorting on the fly. Fine for 20 rows, ruinous for 2 million. |
| `Extra: Using temporary` | Materializing an intermediate result — often a `GROUP BY` the index cannot satisfy. |
| `rows` wildly off from reality | Stale statistics. `ANALYZE TABLE` first, then re-read the plan. |

`FORMAT=JSON` is the one to ask for when the tabular form is ambiguous: it shows
the chosen access path per table with the filtering percentages, which is what
tells you whether the optimizer *believed* your predicate was selective.

## `ANALYZE` — what actually happened

This is the MariaDB feature that ends most arguments. `ANALYZE` **runs** the
query and reports estimated rows next to actual rows:

```sql
ANALYZE FORMAT=JSON
SELECT u.display_name, COUNT(*) AS notes
FROM notes_app.note n ...;
```

<div class="callout callout--tip" markdown="1">
**`r_rows` against `rows` is the whole diagnosis.** If the optimizer estimated
900 rows and actually read 2.4 million, the plan is not wrong — the *statistics*
are, and the fix is `ANALYZE TABLE`, not an index. If the estimate was right and
the query is still slow, the plan is genuinely the problem. Ask the agent to show
you both numbers side by side; that is the sentence worth keeping.
</div>

## Propose an index, then test it somewhere safe

Once the cause is clear, the agent should propose a specific index and say why
the column order is what it is. For the query above that is usually a composite
on the filter columns in equality-then-range order:

```sql
-- notebook_id is an equality predicate, created_at a range: equality first.
CREATE INDEX `idx_note_notebook_created` ON `notes_app`.`note` (`notebook_id`, `created_at`);
```

The `mariadb-create-index` skill supplies the MariaDB-specific constraints the
agent would otherwise get wrong:

- `CREATE INDEX` maps to `ALTER TABLE` — so **batch several additions into one
  `ALTER`** rather than issuing them separately.
- **No functional indexes.** MariaDB has no expression index; you index a
  generated column instead. If the predicate is `WHERE DATE(created_at) = …`,
  no index on `created_at` will ever be used — fix the query or add a generated
  column.
- **Descending indexes are real** since 10.8, which matters for an
  `ORDER BY … DESC` that you want to satisfy from the index.
- **`IGNORED` indexes** let you test the optimizer's behaviour *without* the
  index, without dropping it — the safe way to find out whether an index is
  earning its keep.

<div class="prompt" markdown="1">
*Deploy a sandbox on 3311, recreate `note` and `user` there with the same
structure, seed it with two million rows shaped like production, then measure the
query with and without your proposed index. Show me the `ANALYZE` output for
both.*
</div>

That is the step that turns a suggestion into evidence, and it is only possible
because the sandbox tools are one call away. Nothing touches production.

## Two MariaDB-specific things to check

**Is the predicate sargable?** Wrapping the indexed column in a function —
`DATE(created_at)`, `LOWER(email)`, `CAST(id AS CHAR)` — makes the index
unusable. This is the single most common cause of "the index exists but is not
used", and it does not show up as an error.

**Is an old `utf8` involved?** MariaDB's `utf8` is `utf8mb3`. A join between a
`utf8mb3` column and a `utf8mb4` column converts on every row and cannot use the
index. The `mariadb-create-table` skill flags this, and the table definitions
you asked for at the start are where it shows up — another reason to start
there.

## Write the finding down

<div class="prompt" markdown="1">
*Summarize this into `docs/query-notes-by-notebook.md`: the original query, the
plan before, the cause in one sentence, the index you added, the plan after, and
the measured improvement.*
</div>

<h2 class="no-step" id="what-you-built">What you learned</h2>

- Schema first, plan second. Ask for the table definitions before you let any
  index be proposed.
- `EXPLAIN` is the intent, `ANALYZE` is the truth — and `r_rows` vs `rows`
  distinguishes a bad plan from bad statistics.
- Index proposals get tested on a sandbox, not on production.
- MariaDB specifics that decide the answer: no functional indexes, real
  descending indexes, `IGNORED` indexes for testing, and `utf8` meaning
  `utf8mb3`.

**Where to go next**

- [Throwaway servers](../sandbox-lifecycle/) — more ways to use the rehearsal
  pattern.
- [Version the schema with MSM](../versioned-schema-with-msm/) — so that index
  ships as part of a release rather than as a hand-run statement.
