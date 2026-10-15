---
name: review-shell-change
description: Review a diff, branch, or PR in the MariaDB Shell repository. Runs the standard code review, then applies this repo's policy — what the other CI jobs already cover (so the review stays silent about it), the C/C++ defect classes worth hunting here, and the MariaDB-port conventions needed to judge a guard, a vendor difference, or a gated test correctly. Use this for any review request in this repository, in place of the built-in /code-review.
---

# Reviewing a MariaDB Shell change

This skill is the review entry point for this repository. It does not reimplement
reviewing — it runs the built-in review for the mechanics, then applies the
repo-specific policy the built-in cannot know.

## 0. How to run it

1. **Note what the user asked for.** A PR number, branch or path target, an
   effort level, `--comment` to post inline PR comments, `--fix` to apply
   findings. These pass through unchanged. With no target named, review the
   current diff.
2. **Invoke the built-in `code-review` skill** with those arguments. It owns the
   mechanics: effort levels, the adversarial verification pass, inline comment
   posting, and applying fixes.
3. **Apply §1–§7 below to the result, before anything is reported or posted.**
   Drop the findings §1 puts out of scope, re-rate the ones §2 and §4 change,
   and add anything §3–§5 calls for that the pass missed.

Step 3 matters most when the review runs in a subagent: that agent never saw
this policy, so the filtering has to happen here, in the main context, on what
it hands back. Do not post or report a finding that has not been through it.

Two sections change verdicts rather than adding to them: §1 (a finding the other
CI already reports is noise) and §4 (a guard that looks wrong is usually
correct, and a guard that looks correct is sometimes wrong).

## 1. Out of scope — other jobs already cover these

Seven other workflows build, package and verify this tree. Reporting what they
report wastes the review and trains people to skim it.

- Cosmetic formatting: blank lines, line length, brace placement, indent width,
  clang-format conformance. The pre-commit hook and CI handle it.
- Anything the compiler catches: syntax, types, missing includes, unused
  variables, missing declarations. Every platform build would fail first.
- Copyright headers. The pre-commit hook rewrites them, and it will abort a
  commit that needs one — see `.githooks/pre-commit`.
- Commit message style and changelog entries.

Missing tests **are** in scope, but only where the change alters observable
behaviour and the repo has an obvious home for the test (see §5).

## 2. Formatting that misleads is a correctness finding

The exception to §1, and it is not a style opinion. In C/C++ the layout and the
control flow can disagree and still compile cleanly. Always report, rated by
the damage the divergence causes:

- Indentation implying statements sit inside an `if`/`for`/`while` body when the
  body is unbraced and covers only the first statement — the `goto fail` class.
- A dangling `else` binding to a different `if` than the layout suggests.
- Function-like macros without `do { } while (0)` wrapping that break as an
  unbraced `if`/`else` body, or macro parameters used without parentheses.
- `switch` fallthrough with no comment or `[[fallthrough]]`.
- Any place a reader following the visual structure would conclude something
  different from what the compiler does.

## 3. What to hunt in C/C++ here

The value is in defects that compile cleanly, pass formatting, and are still
wrong. Concentrate on:

- **Lifetime and ownership.** Dangling references and `string_view`s into
  containers that get reassigned; objects freed by the very call that consumes a
  reference into them. This code passes `const &` deep into layers that may
  replace the owner — see §4.3 for the concrete instance of this bug class.
- **Memory safety:** out-of-bounds reads/writes, use-after-free, double-free,
  uninitialized reads.
- **Integer issues:** overflow, signed/unsigned mismatch, truncating casts in
  size/length/index arithmetic before an allocation or a `memcpy`.
- **Unsafe APIs:** `strcpy`, `strcat`, `sprintf`, `scanf` without a width,
  `alloca` on an untrusted size. Flag them even when the current caller is safe.
- **Null dereferences.** See §4.4 — the client library makes these more likely
  here than the same code would be against libmysqlclient.
- **Error paths** that leak (memory, FDs, locks, sockets) or leave an object
  usable in a half-constructed state. Check every early return and throw.
- **Secrets.** Passwords and credentials reaching a log, an exception message,
  a URI, or a core dump. `as_uri()` has password-suppressing formats
  (`formats::full_no_password()`); a review should check the right one is used.
- **Cryptography misuse:** home-rolled crypto, MD5/SHA-1 for security purposes,
  hardcoded keys or IVs, non-constant-time comparison of secrets.

For Python (plugins, test scripts, `mysqlprovision`): command injection via
`shell=True` or string-built argv, `pickle`/`yaml.load`/`eval` on untrusted
input, path traversal, and secrets in messages.

Every security finding states the concrete failure mode, the lines, and a
specific fix. "Consider hardening" is not a finding.

## 4. MariaDB-port conventions

This is the part a reviewer cannot infer from the diff, and where a
well-intentioned review does the most damage by flagging correct code. The full
record is [MARIADB_PORT.md](../../../MARIADB_PORT.md); this is what changes a
verdict.

### 4.1 Which macro gates what

The feature macros are defined in [CMakeLists.txt](../../../CMakeLists.txt)
**exactly when `MARIADB_BUILD` is not** — that is, on ordinary MySQL builds:

| Macro | Gates |
|---|---|
| `HAVE_ADMIN_API` | AdminAPI: `dba`, Cluster / ReplicaSet / ClusterSet, metadata |
| `HAVE_X_PROTOCOL` | X protocol and X DevAPI: `mysqlx://`, collections, X expr parser |
| `HAVE_UPGRADE_CHECKER` | the Upgrade Checker |
| `HAVE_DUMP_AND_LOAD` | the dump/load utilities |
| `HAVE_JS` | JavaScript support, including `--js` and the JS test suites |

Convention: `#ifdef HAVE_X` wraps **MySQL-only** code; `#ifndef HAVE_X` wraps
the **MariaDB stub**. A new guard for one of these features that uses bare
`MARIADB_BUILD` instead is a finding — it hides the intent.

### 4.2 Bare `MARIADB_BUILD` means an intrinsic build difference

After the migration in §1 of the port doc, `MARIADB_BUILD` remains **only** for
differences that are neither AdminAPI nor X-protocol: Connector/C client-API
gaps, mysys lifecycle, Python macro conflicts, the binlog port and its native
GTID model, version/error-code macros, the in-tree `.mylogin.cnf`
implementation. [MARIADB_PORT.md §10](../../../MARIADB_PORT.md) is the
inventory. Judge a new bare `MARIADB_BUILD` against that list; if it is really a
feature gate, it wants a `HAVE_*` macro.

Also: a port-local guard that has become a no-op should be **deleted**, not
left in place. The port doc records current differences, not history.

### 4.3 Connection options are owned by the low-level session

`ShellBaseSession::get_connection_options()` returns a reference into the
low-level session. Any caller that then connects or reconnects destroys the
owner of that reference. Callers must hold a **copy**:

```cpp
const auto co = session->get_connection_options();  // copy, not const &
session->connect(co);
```

A `const auto &` here is a use-after-free, not a style preference. This is the
most likely lifetime bug in session code and worth checking on sight.

### 4.4 libmariadb segfaults where libmysqlclient tolerated

libmariadb dereferences a `NULL MYSQL *` in places libmysqlclient handled
safely. Accessors that reach `_mysql` need a null guard even when the
equivalent MySQL-targeted code did not. Treat a new unguarded `_mysql` access
as a crash, not a nit.

### 4.5 Vendor differences are runtime, not compile-time

Server behaviour that differs between MySQL and MariaDB is decided at runtime
through `ISession::get_server_vendor()`
([session.h:130](../../../mysqlshdk/libs/db/session.h#L130), returning
`ServerVendor::{MySQL, MariaDB}`) — **not** by `#ifdef MARIADB_BUILD`. A
MariaDB-targeted build must still talk to MySQL servers, so a compile-time guard
around a server behaviour difference is a bug. Watch for it in dump/load,
schema_dumper, and anything reading server metadata.

Known behaviour differences worth remembering when judging a change: MariaDB
never emits `sql_mode` via session tracking (the shell must refresh
explicitly); check constraints are enforced per session, not per constraint;
sequences filter as tables and cache ahead; GTID positions are per domain, and
`SHOW MASTER STATUS`'s fifth column is not the one you want.

## 5. Test gating

Two mechanisms, and picking the wrong one is a finding:

- **`__mariadb_build`** — a *build* flag, defined at
  [shell_script_tester.cc:1799](../../../unittest/shell_script_tester.cc#L1799).
  Use it for chunks that depend on a feature this build excludes:
  `#@ ... {__mariadb_build}` / `{not __mariadb_build}`.
- **`sandbox.vendor()`** — the *server* vendor, `"MySQL"` or `"MariaDB"`. Use it
  for chunks that depend on server behaviour:
  `#@ ... {sandbox.vendor() == "MySQL"}`.

Gating a server-behaviour difference on `__mariadb_build` conflates the two and
breaks the moment someone runs a MariaDB build against a MySQL server. Flag it.

Note the unittest `GLOB` gotcha: excluding a test source from the build is not
enough if a `GLOB` picks it back up — check both.

## 6. Design-level simplicity only

Flag overengineering: abstraction layers, interfaces, templates, config options
or "future-proofing" the change does not require. Prefer deleting code to adding
it. Flag AI-slop patterns — comments restating the code, boilerplate docstrings,
try/except around code that cannot fail, dead code, a helper that already exists
elsewhere in the tree.

Do **not** flag naming taste or style. This section is about code that is harder
to reason about than the problem requires, nothing else.

## 7. Discipline

- Read enough surrounding code to be confident. If a finding cannot be verified
  from the code available, say so instead of guessing.
- No praise padding, no summary of what the change does, no restating the diff.
  Findings only.
- If there are no findings, say so in one line. Do not invent any.
