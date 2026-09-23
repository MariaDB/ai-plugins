---
order: 10
slug: compare-server-versions
title: "Check a schema against two MariaDB versions at once"
description: >-
  Deploy two sandboxes on different major releases, run the same create script
  on both, and diff what the servers actually did with it. The cheapest way to
  find out whether a schema is portable across the versions you have to support.
level: intermediate
duration: "35 min"
area: sandbox
tools: ["sandbox.list_available_versions", "sandbox.deploy", "db.connect", "db.execute_sql_script", "db.get_object_details", "sandbox.kill", "sandbox.delete"]
skills: ["mariadb-features", "mariadb-create-table", "mariadb-schema-create-script"]
path_label: "Operate and Optimize, Step 4"
prerequisites:
  - "[Tutorial 1](../notes-app-sandbox/) — you need a create script to test. `notes_app.sql` from that tutorial is exactly right."
  - "The working directory on the MCP server's allowed-paths list."
  - "Nothing else. Neither version has to be installed; the sandbox downloads what it needs."
---

"Does this schema work on the version our customers actually run?" is normally
answered by someone finding a spare machine. It does not have to be: two
sandboxes on two releases cost one instruction, and the servers download
themselves.

<div class="prompt" markdown="1">
*Which MariaDB server versions can you deploy? Then deploy a sandbox on the
newest 11.8 on port 3311 and one on the newest 12.3 on port 3312, run
`notes_app.sql` on both, and tell me every way the two results differ.*
</div>

## See what you can actually deploy

<div class="prompt" markdown="1">
*Which MariaDB server versions can you deploy on this machine?*
</div>

That question becomes a tool call the agent makes on your behalf:

```text
sandbox.list_available_versions()
  → 11.8.9, 12.3.3
```

By default you get the **newest patch of each release series**. Ask for a series
— *"every 11.8 release"*, or *"everything on 11"* — to see the patches below it.

Two things this list is telling you, and both matter here:

- **It is filtered to your platform.** A version appears only if a package is
  built for the machine you are on, so anything listed can definitely be
  deployed.
- **It is a static index inside the plugin, not a live lookup.** What you can
  install is fixed by the plugin version you have, which makes a run
  reproducible — and means a newly published server release arrives with a
  plugin update, not on its own.

## Deploy both

<div class="prompt" markdown="1">
*Deploy a sandbox on the newest 11.8 on port 3311 and one on the newest 12.3 on
port 3312.*
</div>

Pin as much or as little as you care about. "The newest 11.8" and "anything on
11" are both valid asks, and so is `11.8.9` exactly — each level you leave off is
filled in with the newest release below it.

<div class="callout callout--tip" markdown="1">
**Read the deploy message — it tells you where the server came from.** It says
**found on the PATH**, **already downloaded**, or **downloaded now**. The first
is instant, the last is a package download, and knowing which you are waiting
for is the difference between "this is slow" and "this is fine".

If one of your two versions happens to match the server on your `PATH`, that one
deploys instantly and the other downloads. That asymmetry is the resolution
order doing its job, not a fault.
</div>

<div class="callout callout--warn" markdown="1">
**A downloaded server cannot be shut down gracefully.** The graceful path needs
the server binary on the `PATH`, and a downloaded one is not there — so the
agent has to force these instances down instead. It handles that on its own; the
thing that matters for your prompt is to ask for the cleanup in a way that
tolerates it, which the teardown prompt below does.
</div>

## Confirm you got what you asked for

Never take the version from the request. Take it from the server:

<div class="prompt" markdown="1">
*Connect to both sandboxes and run `SELECT VERSION()` on each, so we are
comparing what the servers say rather than what we asked for.*
</div>

This is what the agent will execute:

```text
sandbox.version(port=3311)   → 11.8.9
sandbox.version(port=3312)   → 12.3.3
```

## Run the same script on both

<div class="prompt" markdown="1">
*Run `notes_app.sql` against both sandboxes.*
</div>

Both connections were registered automatically when the sandboxes were deployed,
so there is no setup step between here and there.

This is the moment the exercise pays for itself. A script that **fails on one
version** has told you something immediately. But the more interesting case is
the one that *succeeds on both* — because succeeding is not the same as doing
the same thing.

## Diff what the servers actually did

Comparing the script to itself proves nothing. Compare the schemas the two
servers ended up with:

<div class="prompt" markdown="1">
*For every table in `notes_app`, pull the column types, defaults, collations,
indexes and constraints from both servers and show me only the differences.*
</div>

Insist that it reads this **out of the servers** rather than inferring it from
the script it just ran — the whole point is that the script does not tell you
what the servers did with it. A query that makes the comparison concrete:

```sql
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE,
       COLUMN_DEFAULT, COLLATION_NAME, EXTRA
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = 'notes_app'
ORDER BY TABLE_NAME, ORDINAL_POSITION;
```

Run it on both, diff the two result sets. Things that genuinely differ between
releases, and are invisible in the script that produced them:

- **Default collation.** The `utf8mb4` default collation has changed across
  MariaDB releases. Two servers can accept the same `CREATE TABLE` and end up
  sorting and comparing differently — which surfaces much later as a `UNIQUE`
  constraint that behaves differently on two machines.
- **What the optimizer records.** Index statistics and histogram defaults move
  between versions.
- **Reserved words.** A column called `vector` is fine until a release makes it
  a keyword. Backticking everything, as the `mariadb-schema-create-script` skill
  insists, is what makes this a non-issue.
- **Deprecations that still parse.** A clause can be accepted with a warning on
  the newer server. Warnings are not errors, so a green run hides them.

<div class="prompt" markdown="1">
*Re-run the script on the 12.3 sandbox and show me `SHOW WARNINGS` after each
statement. Anything deprecated?*
</div>

## Try the thing you are actually unsure about

The two-sandbox setup is a bench, not a one-off. Once it exists, use it for the
specific question you had:

<div class="prompt" markdown="1">
*Add a system-versioned table to the script and run it on both again — is the
behaviour identical?*

*Insert the same 10,000 rows into both and compare `EXPLAIN` for our slowest
query. Do the two versions pick the same plan?*

*Does `ALTER TABLE note ADD COLUMN … NOT NULL DEFAULT …` use `ALGORITHM=INSTANT`
on both?*
</div>

That last one is a genuinely common surprise: the set of changes that can be
done instantly has grown release by release, so an `ALTER` that is instant on
12.3 may rewrite the whole table on 11.8. Measuring it costs one sandbox pair.

## Clean up both

<div class="prompt" markdown="1">
*Stop and delete both sandboxes, even if one of them fails.*
</div>

"Even if one of them fails" is doing real work in that sentence. At least one of
these servers was probably downloaded rather than found on the `PATH`, so it has
to be forced down rather than stopped gracefully — and a sandbox cannot be
deleted while it is still running. Phrasing the teardown so a failure does not
abandon the second instance is the difference between a clean machine and two
orphans.

The **downloaded server packages are deliberately not removed** by
`sandbox.delete`. They live one directory per version under
`~/.local/share/mariadb-sandbox-server/`, and keeping them is the point: the next
deploy on that version is instant. Delete those directories by hand if you want
the space back.

<h2 class="no-step" id="what-you-built">What you learned</h2>

- Ask what versions are available first; anything listed can be deployed, and it
  downloads itself if it has to.
- Pin as much of the version as you care about — `11.8.9`, `11.8` or `11` — and
  the newest match fills in the rest.
- The agent tells you where each server came from; a downloaded one cannot be
  stopped gracefully, so ask for teardown that tolerates a failure.
- **Running on both is the easy half; diffing the resulting schemas is the
  half that finds things.** Read the result out of the servers, and check
  warnings, not just exit status.

**Where to go next**

- [Throwaway MariaDB servers](../sandbox-lifecycle/) — the rest of the
  `sandbox.*` group.
- [Diagnose a slow query](../diagnose-a-slow-query/) — now with two versions to
  compare plans between.
- [Ship a schema upgrade](../ship-a-schema-upgrade/) — where a version-portable
  schema actually pays off.
