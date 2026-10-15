---
name: mariadb-migrator-run
description: "Execute a MySQL-to-MariaDB migration with migrator.plan, migrator.run and migrator.resume — always plan first, omit `out` on a new run so a stale state.json cannot report every step SKIPPED at exit 0, check a finished run three ways (succeeded, every step DONE, the data actually on the target), read report.json/run.log in the artifacts directory, and hold the source baseline instead of publishing an interim report. Use when starting, timing out, resuming or diagnosing a migration run, or when a run reported success but nothing moved. Read mariadb-migrator first for the tools and preconditions."
---

# Migration — Plan, Then Run

```text
1. db.list_connections()                    # what may be named at all
2. migrator.set_config(mode=..., env=...)   # refused unless it is right
3. migrator.plan(mode=...)                  # executes nothing; validates
4. migrator.run(mode=...)                   # omit `out` — fresh directory
5. verify on the target with the db.* tools
```

Steps 1–2 are `mariadb-migrator-discovery` and `mariadb-migrator-configure`;
step 5 is `mariadb-migrator-verify`.

**Always `plan` first.** It costs nothing, reaches no server, and tells you
whether the mode and the configuration are complete — including which steps the
run will perform. Re-`plan` after every `merge=True` correction too.

**Then check a run three ways**, because any one of them can pass while the
migration did nothing:

1. `succeeded is True` and `exit_code == 0`;
2. **every step in `report` has `status: "DONE"`** — all `SKIPPED` means a reused
   `out` directory, and the run exited 0;
3. the data is actually on the target — query it.

The run returns `out_dir`, `install_dir` and the parsed `report`; the run's own
`report.json` and `run.log` live in `<install_dir>/<out_dir>` and are the real
diagnosis when a step fails. `stdout`/`stderr` are only the tail.

The default timeout is one hour. A large migration can outrun it; the artifacts
directory is returned either way, so a run that is stopped can be picked up with
`migrator.resume(mode=..., out=<the same out_dir>)`. `out` is required for
`resume` and must stay relative to the install directory.

What `resume` does **not** resume is the data copy inside mode 2 — see
`mariadb-migrator-modes` before promising restartability.

## While a large run is still in progress

On a large migration, it's reasonable to gather the source-side baseline
(counts, silent-loss checks) while `run` is still working in the
background — that data doesn't change once the dump has started, so
collecting it early is efficient. But **collect it silently and hold it —
don't publish it as an interim report.** A standalone "here's what the
source looks like" table, or a rundown of which silent-loss risks were
ruled out, is noise while the actual outcome is still unknown, and it
duplicates work the operator will read again in the final report anyway.

Say only that the run is in progress and roughly what it's moving (e.g. "59M
rows, still running") if anything at all — hold everything else (the
baseline table, the silent-loss check results) for the **final comparison
table** in `mariadb-migrator-verify`, once the run completes and there's a
target side to put next to it. The source numbers you gathered early become
the "Source" column then; nothing about them needs to be said twice.

## See Also

- `mariadb-migrator` — the overview: tools, preconditions, modes at a glance.
- `mariadb-migrator-configure` — the configuration `plan` validates.
- `mariadb-migrator-modes` — mode 2's resume caveat and mode 3's phases.
- `mariadb-migrator-verify` — the verification and report that follow a run.
- `mariadb-migrator-troubleshooting` — what a failure message means and what to set.
