---
name: mariadb-migrator-discovery
description: "Turn a bare MySQL-to-MariaDB migration request into something runnable — call db.list_connections, probe and present source and target in one table, list the migratable schemas, and know when a fully-specified request may go straight to run and when a name that matches no configured connection is a hard stop. Use when a migration is asked for without a source, target, schema or mode named, when deciding what to ask before configuring a migration, or when the names in the prompt do not appear in db.list_connections. Read mariadb-migrator first for the tools and preconditions."
---

# Migration — Starting From a Bare Request

A prompt like "I want to migrate from MySQL to MariaDB," with no source,
target, schema, or mode named, is the normal starting point, not a request
to ask five questions up front. Do the discovery yourself.

See `mariadb-migrator` for the tooling, its preconditions and the four tools.

## The discovery pass

1. **Call `db.list_connections`.** If it returns none, stop here and instruct
   the operator to add one: `mariadb-shell -- mcp setup --addConnection`.
   There is nothing else to do until at least a source and a target exist as
   configured connections.
2. **Probe each connection, and display source and target together in one
   table** — host and account combined into a single column (`user@host:port`),
   the same way the target is already identified, not host and account split
   across columns:

   | Host / Account | Server | Role |
   | --- | --- | --- |
   | `mig_native@mdb-o:3306` | MySQL 8.4.7 | source |
   | `mig_native@mdbvm2:3306` | MariaDB 11.8.9 | target |

   Report which are reachable and which aren't — an unreachable connection
   is still useful information, don't hide it. Privilege validation for an
   account happens at `mcp setup --addConnection` time, not here — a
   connection that's configured and reachable is usable as-is. **Exception:**
   for a mode 3 `load_only` request, skip probing the source entirely — see
   `mariadb-migrator-modes` for why.
3. **List the migratable schemas** on any working source (name, table
   count is enough) so the operator can pick one without first running their
   own discovery query.

## When the request already answers all of it

Once connections exist, the operator can shortcut all of this by stating it
directly: *"migrate database abcd from mysqlhost to mariadbhost using mode
1"* (mode can be 1, 2, 3, or 4). Skip whichever parts of the discovery above
that statement already answers.

**A complete instruction like that can go straight to configuration and
`run` in one pass — no confirmation prompts in between — as long as every
precondition check for the named mode also comes back clean**: the named
source and target resolve to configured connections, the schema exists, and
anything mode-specific (e.g. `mariadb-mtk` for mode 2, no `JSON` columns for
mode 4) checks out on its own. Only fall back to asking when one of those
checks actually turns up something missing or wrong — a fully-specified,
fully-clean request doesn't need to be slowed down by asking anyway.

## When the names don't resolve — a hard stop

**If the named source/target/schema in the prompt don't resolve to
configured connections, that is a hard stop — never fall back to whatever
is already sitting in `config/migration.yaml` from a previous run and
execute that instead.** A leftover config satisfying the tooling's
preconditions is not the same thing as the operator asking for that
migration in this turn. This applies doubly when the input doesn't look
like a migration request at all — e.g. it resembles a `mariadb-mtk` CLI
invocation, a fragment, or names (like `testhost`/`mysqlhost`) that appear
nowhere in `db.list_connections`. `migrator.run` changes a real target;
confirm what's actually wanted before calling it rather than guessing from
stale state. Say plainly that the names given don't match a configured
connection, show what's actually available, and ask what to do — don't run
anything in the meantime.

## When the mode isn't stated

**If the mode isn't stated, ask for it rather than picking one silently** —
give the short version of the mode table (name and one-line tradeoff for
each, as in `mariadb-migrator`) so the operator can choose without reading
the full reference in `mariadb-migrator-modes`. Mode 1 being the documented
default doesn't mean assume it; it means offer it as the recommendation when
asking.

## See Also

- `mariadb-migrator` — the overview: tools, preconditions, modes at a glance.
- `mariadb-migrator-modes` — the full mode reference and each mode's gates.
- `mariadb-migrator-configure` — writing the configuration once discovery is done.
