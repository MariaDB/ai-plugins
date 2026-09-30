---
name: split-scripted-test
description: Split a long scripted test (unittest/scripts/auto/*/scripts/*_norecord.py) into N parallel chunk groups for run_unit_tests.py, or rebalance the groups of a test that is already split, so every group takes about the same time. Use when asked to split, shard, parallelize, balance or rebalance a scripted test, change its number of groups, or find out why one group of a split test is slower than the others.
---

# Splitting and balancing a scripted test

`scripts/run_unit_tests.py` (the `rut` task) runs a test listed in
`_SPLIT_TEST_GROUPS` as N tasks with `GROUP_ID` = 1..N. A chunk whose header ends
in `(G)` runs only in group G; a chunk with no suffix runs in every group. The
goal is N groups, in file order (group 1 first … group N last), that finish at
the same time. Every group must still pass on its own.

The mechanics are in `scripts/balance_chunk_groups.py`, and its docstring is
the reference for them. This skill covers the procedure and the judgement calls
that the script can't make.

## Tools

- **Timing collection is automatic.** `shell_script_tester.cc` records every
  executed chunk to `$CHUNK_TIMINGS_FILE`. `run_unit_tests.py` sets that variable
  for every task and merges the results of **passing** tasks into
  `test-chunk-times.txt`, next to the `-t` file (`unittest/`). Chunks that run
  in every group are averaged.
- **`balance_chunk_groups.py <script> <N> [--explain] [--write]`** splits the
  grouped chunks into N contiguous groups, minimizing the slowest one. It never
  cuts through a detected dependency. Without `--write` it prints a table and a
  diff.
- **`balance_chunk_groups.py <script> --init`** does the first split of an
  unsplit script. It gives every chunk except the INCLUDEs, `entry point`,
  `Setup` and `Cleanup` (plus any `--common ID`) a `(1)` placeholder for the
  balancing step to renumber.
- **`balance_chunk_groups.py <script> <N> --estimate`** balances by each chunk's
  line count instead of its timings. It gives a provisional split for a script
  with no timings yet.
- **`balance_chunk_groups.py --merge FILE --skip PREFIX`** merges a **failed**
  task's timings, leaving out its failing chunks. The timings are in
  `<logs-dir>/workerW/T/chunk-timings.txt`.

## Running the test

Run it the way `rut` does, so the timings reflect real parallelism. Take the
server from `.vscode/settings.json` (`env.main-server`, `env.mysql-port`), as
the `rut` task in `.vscode/tasks.json` does. Keep the plan, report and log files
out of `bld/bin`:

```sh
cd bld/bin && MYSQL_PORT=3311 PATH=~/servers/<main-server>/bin:$PATH \
  python3 ../../scripts/run_unit_tests.py --binary ./run_unit_tests \
  --shell-binary ./mariadb-shell -t ../../unittest/test-execution-times.txt \
  --gtest_filter='*<test_name>' --execution-plan-file <tmp>/plan.txt \
  --report-file <tmp>/report.html --logs-dir <tmp>/logs
```

Rebuild `run_unit_tests` first if the tester has changed. A run takes about as
long as the slowest group; an unsplit test takes its whole length (10+ minutes
for the copy tests), so run it in the background.

**Run it against MySQL too**, from the MySQL-linked build (`bld-mysql/bin`)
with a MySQL server first on `PATH` (`~/servers/<version>/bin`). Remove every
MariaDB server directory from `PATH` as well: the runner and the harness pick
the vendor from the first `mariadbd`/`mysqld` on `PATH`, and `mariadbd` is
looked for first. Pass a `-t` file of its own, such as
`../../unittest/test-execution-times-mysql.txt`. Chunk timings are still merged
into the shared `test-chunk-times.txt` next to it, so a MySQL run overwrites
MariaDB's timings for every chunk it times. Rerun on MariaDB before you
rebalance.

## Procedure

1. **Measure.** For a split test, the last `rut` run's timings are usually
   enough. For an unsplit test, either run it once as it is (fine if it takes a
   few minutes), or, for a long test, skip ahead: do the first split with
   `--estimate`, run that split (about 1/N of the time), and rebalance on the
   timings it records.
   - If a group failed, read its `test-output.log`. Failures are often porting
     problems that also distort the timings; see Pitfalls.
   - Fix what's in scope, then `--merge --skip` the failed task's timings.
   - Timings are keyed by chunk id, so they stay valid when the number of groups
     changes.
2. **First split** (unsplit test only):
   - Run `--init`. Check that the chunks it left common really are needed in
     every group, using `--common` for extra setup chunks.
   - Add the test to `_SPLIT_TEST_GROUPS` with N.
3. **Balance.** Run `balance_chunk_groups.py <script> N --explain` and read the
   output:
   - **The table** shows each group's `current` and `balanced` time, including
     the chunks common to every group.
   - **A slowest group made of one big block** means a dependency is holding a
     large range together; `--explain` names it. Don't move code to break it.
     See "Keeping the diff small".
   - **The cuts** list the chunks on either side of every group boundary. Check
     each one by reading the code (next step).
4. **Review every cut by hand.** The script only sees Python-level dependencies
   (variables and functions defined in an earlier chunk, setup…cleanup runs,
   consecutive `BUG#nnn` chunks). It can't see state left on disk or in the
   server by an earlier chunk, such as a dump directory, a created schema, or a
   switched session user. A safe group start begins with its own
   `EXPECT_SUCCESS`/dump, a `TEST_*_OPTION`, or a wipe and setup of its own.
   - For a dependency the script misses, put
     `# balance: keep-with-previous` in the dependent chunk. Add it even when the
     current cut is fine, so a later rebalance won't split the pair.
   - For a longer run that must stay together, put `# balance: begin-block` in
     its first chunk and `# balance: end-block` in its last. The typical case is
     `prepare user privileges, switch user` … `reconnect to the user with full
     privileges`: every chunk between them runs as the restricted test user.
     dump_tables and dump_instance already carry these markers.
   - A chunk reading a variable left over from an earlier chunk (for example a
     loop variable) is a real dependency. Define it locally, adding one line,
     rather than keeping the whole range together.
   - For a false positive, use `# balance: allow-cut-before`.
   - **Also check every chunk that looks at the whole instance**, not only the
     ones next to a cut: a `dump_instance`, a dump or `EXPECT_SUCCESS` with no
     schema filter (`None`), `compare_servers()`, `snapshot_instance()`, or an
     asserted total such as "N indexes were built" or "N tables". Such a chunk
     depends on what *every* earlier chunk left on the server, including the
     groups it no longer runs after. In file order it may run after a wipe
     (`wipeout_server()`, `drop_all_schemas()`) that its group no longer
     includes, or it may count something another group leaked. See "Hidden
     whole-instance state" below.
5. **Write** with `--write`, then run the test split. All groups must pass,
   **on both vendors**: run it against MySQL as well as MariaDB (see "Running
   the test"). That run also records timings with real parallelism.
6. **Rebalance only if it's worth it.** Rerun the balancer on the fresh timings.
   A gain of a few percent on the slowest group is within run-to-run noise and
   isn't worth the churn of moving suffixes. About 10% or more is worth it.
   After rebalancing, rerun.
7. After code changes, run `graphify update .`.

## Keeping the diff small

These test files are compared with upstream MySQL Shell, so:

- **Never move chunks.** Group suffixes are expected to change. Moving code
  makes the diff unreadable.
- **When a dependency welds a big range together**, split the defining code off
  into a **new common chunk**: a new `#@<> ...` header with no suffix. For
  example, dump_tables' `WL13804-FR13 - CRC of the test schema tables…` adds two
  lines and frees the whole range. When the definition sits in the middle of an
  expensive chunk, you can instead repeat a cheap assignment in a new common
  chunk right **after** it, which leaves the original untouched; see
  dump_instance's `targetVersion used by the MySQL HeatWave Service tests
  below`. The new chunk runs in every group, so it must
  be cheap, and it must be safe to run on whatever state each group has at that
  point.
- **A long block held together by session or schema state** can often be
  split by making its **cheap** setup and teardown chunks common, instead of
  keeping everything between them in one group. Every group then runs that
  stretch of the file in the same state as the unsplit run: for example, as the
  restricted user between a "switch user" chunk and its "reconnect" chunk.
  Then pin only what really shares state. Check the cost first: every group
  pays for the common chunks.
- **But keep CPU-heavy chunks together.** Chunks that start background load
  (`Generate_transactions`, which creates 500 tables and runs a DDL/DML loop in
  another shell) slow each other and every other group down when they run in
  parallel groups. The balancer can't model that, because it treats chunk
  times as independent. In dump_instance, spreading them over three groups
  raised the slowest group from about 300s to 407s, and even groups that hadn't
  changed got 10–15% slower. They're now one `begin-block`…`end-block`. Timings
  recorded while such chunks overlapped are inflated, so rerun with them
  serialized before trusting a rebalance.
- **An empty `()` suffix is not a group.** The tester treats it as "run
  everywhere". The balancer assigns it a real group.

## Hidden whole-instance state

A chunk that dumps, compares or counts the whole instance can pass in file
order only because of something another group did, or because of a leftover
that group never cleaned up. Splitting then breaks it in a way no cut review
catches. Both cases below were found only by a MySQL run: the chunks are
`not __server_is_maria_db`, so a split verified on MariaDB never ran them.

- **A wipe in an earlier group.** util_dump_instance's `BUG#35550282 - option
  is set, schema is not dumped` does an `ocimds` dump of the whole instance.
  In file order it runs after the `WL14244` helpers have run
  `wipeout_server()` and `WL15311 - setup` has re-created the test schemas
  empty. Its group ran neither, so it still had the deliberately incompatible
  `mysqlaas` fixtures, and the compatibility check failed. **Fix:** make the
  chunk's own setup restore the state it has in file order (here
  `drop_all_schemas()` + `create_all_schemas()`), rather than pinning it to the
  earlier group.
- **A leak in an earlier group.** util_dump_and_load's `BUG#33414321 - table
  with a secondary engine` asserted that 13 indexes were built for the whole
  instance. One of the 13 was `wl14506.no_pk`'s, left on the source server
  because `WL14506: cleanup` ran `DROP SCHEMA` on the global `session`, which
  `EXPECT_PK()` had switched to the destination. **Fix:** fix the leak
  (`WL14632: cleanup` had the same bug), then correct the expectation to the
  count without it, so it holds in every order.

What to look for:

- **Cleanups that use the global `session`** after a helper that calls
  `shell.connect()`. They clean the wrong server, and the leftovers show up
  later, in one group only. Drop through the named sessions (`session1`,
  `session2`) instead.
- **Hard-coded totals over the whole instance**, such as index, table or file
  counts. In a split run the total only matches if every group sees the same
  instance.
- **To confirm a suspected case**, run the test unsplit (see Pitfalls for how).
  If the chunk passes there and fails in its group, it is this class and not a
  product bug.

## Pitfalls

- **Timings depend on parallelism.** Eight workers make each group about 25%
  slower than six do, so compare groups within the same run.
- **The `rut` server may be a debug build** (`mariadbd --version` shows
  `-debug`). It is about 3× slower per row in `LOAD DATA`, which inflates every
  dump/load/copy chunk. The balance still holds; the absolute times don't.
- **`VER(>=8.2.0)` passes on MariaDB 12+.** MySQL-only chunks guarded only by
  version, for example `WL15887` HeatWave account checks, then run on MariaDB and
  fail. Gate them with `and not __server_is_maria_db`: the setup, the tests
  **and** the cleanup. If only the cleanup is gated, a debug point such as
  `copy_utils_force_mds` set in the setup stays on and breaks every later chunk
  in that group.
- **`copy_utils_force_mds` enables the `ocimds` checks**, which MariaDB rejects.
  A MariaDB variant of such a test must not set it.
- **Flaky under load:** `WL15298 - test sessionInitSql option` in copy_schemas
  has deadlocked once (1213): four loader threads insert into the same table.
  Before blaming a new cut for a failure, check whether the chunk depends on
  anything before it.
- **A baseline must run with no `GROUP_ID` at all.** The tester runs only
  group G's chunks when `GROUP_ID` is set, even to `0`. `run_unit_tests.py` now
  leaves it unset for tasks that aren't split; before that fix, an unsplit run
  of a tagged script "passed" while running only its common chunks. To get an
  unsplit baseline of a split test, run a copy of `run_unit_tests.py` with the
  test's `_SPLIT_TEST_GROUPS` line removed, and check that its duration makes
  sense.
- **Group totals barely include overhead.** The .inc files take under 0.1s and
  process start/teardown about 1s. The common chunks cost what `Setup` costs,
  usually a sandbox deployment. `run_unit_tests.py` builds the sandbox
  boilerplate once per run and shares it through
  `MARIADB_SANDBOX_BOILERPLATE_DIR`, so a deployment is a copy, not a
  `mariadb-install-db`; that took copy_schemas' `Setup` from 27s to 10s per
  group. If a test's Setup suddenly costs about 20s more, check that the runner
  still printed "Preparing the sandbox boilerplate…".

## Reporting

Report to the user:
- the predicted per-group table, and the measured one after the split run;
- the slowest group and what limits it (for example, one indivisible block);
- each marker or new common chunk you added, and why;
- every failing chunk, split into "caused by the split" and "already failing";
- which vendors the split was run on. A split verified on one vendor only has
  not run the other vendor's gated chunks.
