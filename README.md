# MariaDB AI Plugins

First-class **MariaDB** support for AI coding agents. This repo packages a
curated set of agent **skills** and wires up the native, high-performance
**`mariadb-shell` MCP server**.

Installing a plugin gives you three things:

- **Skills** — MariaDB reference material the agent reads when it becomes
  relevant: how `ALTER TABLE` behaves in MariaDB, how vector indexes work, which
  connector to use from Python or Java, how to move an application over from
  MySQL. Skills work straight away and need no database.
- **An MCP server** — a live connection to a MariaDB server, so the agent can
  read your schema, run queries, analyse a slow query with `EXPLAIN`, or start a
  throwaway test instance. This needs a one-time setup, described below.
- **`mariadb-shell`** — MariaDB's command-line shell, a port of MySQL Shell,
  installed automatically the first time an agent starts the MCP server. The MCP
  server runs inside it as a plugin, and it is where your database credentials
  are stored. You can also use it yourself as a SQL client — run `mariadb-shell`
  and type `\help`.

> **New to MCP?** The Model Context Protocol is how an AI agent calls tools —
> here, the tools that talk to MariaDB.

Works with [Claude Code](https://claude.com/claude-code),
[Codex](https://openai.com/codex), [OpenCode](https://opencode.ai) and
[Pi](https://pi.dev) — see [Installation](#installation).

## Installation

### Claude Code

```text
/plugin marketplace add mariadb/ai-plugins
/plugin install dev@mariadb
```

### Codex

```text
/plugin marketplace add mariadb/ai-plugins
/plugin install dev@mariadb
```

Then register the MCP server, which the plugin cannot do for itself on Codex
0.147 — it stores a plugin's `command` verbatim and expands no placeholder, so the
server would fail to start:

```sh
codex/dev-plugin/scripts/setup-codex-mcp.sh     # --remove to unregister
```

On native Windows run the batch counterpart instead — it registers the `.cmd`
launcher, which is the one Codex can actually spawn there:

```bat
codex\dev-plugin\scripts\setup-codex-mcp.cmd
```

Reload (`/reload-plugins`) if Codex doesn't pick it up automatically. See
[codex/dev-plugin/README.md](codex/dev-plugin/README.md) for details.

### OpenCode

OpenCode has no central marketplace. Merge the `mcp` block from
[opencode/dev-plugin/opencode.json](opencode/dev-plugin/opencode.json) into your
`opencode.json`, point `MARIADB_DEV_PLUGIN` at the plugin dir, and symlink its
flat `skills/` into an OpenCode skills directory. Full steps in
[opencode/dev-plugin/README.md](opencode/dev-plugin/README.md).

### Pi

Pi installs the repo itself as a package (the `pi` field in the root
`package.json`), then the MCP server is registered once with the adapter:

```sh
pi install npm:pi-mcp-adapter                              # once — connects pi to MCP servers
pi install git:github.com/mariadb/ai-plugins   # this repo (skills + extension)
# …or from a local checkout, at the repo root: pi install .
```

```text
/mariadb-mcp-setup            # in pi: writes the global ~/.config/mcp/mcp.json
/mariadb-mcp-setup --project  # or ./.mcp.json for just this project
```

Then `/mcp reconnect mariadb` (or restart pi). The extension also prints a
one-line reminder at session start while the server isn't configured. Full steps
in [pi/dev-plugin/README.md](pi/dev-plugin/README.md).

## Configure the MCP server (all harnesses)

The skills work on their own. The MCP server, however, starts out allowed to reach
nothing — installing a plugin wires it up, but does not tell it what it may touch.
Run this once per machine:

```sh
mariadb-shell -- mcp setup     # or mcp.setup() from an interactive shell
```

> **Why the shell?** It already handles connections, credentials, test instances
> and schema management, so the MCP server runs as a plugin inside it rather than
> reimplementing all of that.

If `mariadb-shell` isn't on your `PATH`, use the copy the launcher installed —
`~/.local/bin/mariadb-shell`, or
`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd` on Windows. The
installer only prints a `PATH` hint; it never edits your shell profile. That copy
appears the first time a plugin starts the MCP server, so either let the agent run
once first, or install the shell yourself before configuring it.

## What you can ask for

**With skills alone**, no database connection needed:

> *Write a `CREATE TABLE` for a product catalogue, MariaDB style.*
> *What changes if I move this application from MySQL to MariaDB?*
> *How do I do semantic search in MariaDB?*
> *Show me how to connect to MariaDB from Node.js.*

**With the MCP server connected**, against your real database:

> *What does the schema of my `orders` table look like?*
> *Why is this query slow? Run `EXPLAIN` on it.*
> *Which of my tables have no primary key?*
> *Deploy a test instance and try this migration on it first.*

**No database yet?** The MCP server can deploy a throwaway MariaDB instance
locally — no Docker, no container runtime, no administrator rights:

> *Deploy a MariaDB sandbox on port 3310.*
> *Spin up a test instance, apply this schema to it and show me the result.*
> *Try this migration on a sandbox before I run it for real.*
> *Stop and delete the sandbox, I'm done with it.*

Instances live under `~/.mariadb-shell/sandboxes/<port>/`. Three things to know:
a sandbox is **not** automatically a connection the agent can use — register it
with `mariadb-shell -- mcp setup` first; it is deployed without TLS, so
command-line clients may need `--skip-ssl`; and it creates a `root@'%'` account
and listens on all interfaces, which is worth changing outside a trusted network.

The MCP server provides 27 tools in three groups:

| Group | Tools | What they do |
| ----- | ----- | ------------ |
| `db.*` | 8 | list connections and schemas, describe objects, run SQL |
| `msm.*` | 12 | MariaDB Schema Management — versioned schema projects, releases, deployments |
| `sandbox.*` | 7 | deploy, start, stop and delete local throwaway server instances |

## Plugin variants

Each agent ships the plugin variants below — all built by the same
[scripts/sync-skills.sh](scripts/sync-skills.sh):

| Plugin | Skills | MCP server | Skills source |
| ------ | ------ | ---------- | ------------- |
| `dev` | full set — statements, functions, client tools, connectors, topical (+ all local `additional-skills/`: `sql`, `rest`, `schema-management`) | yes | `mariadb-docs` + `additional-skills/` |
| `sql` | SQL-focused subset — statements, functions, topical (+ local `additional-skills/sql`) | yes | `mariadb-docs` + `additional-skills/sql/` |
| `contributor` | skills for **contributing to MariaDB tooling** | no | [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell) `.claude/skills/` (private) |

The folders are `<agent>/{dev,sql,contributor}-plugin/` for each of `claude/`,
`codex/`, and `opencode/`; `pi/` ships `dev` only for now. Skills are baseline
**MariaDB 11.8 LTS**; the `dev` and `sql` plugins share the same auto-downloading
`mariadb-shell` MCP server, while `contributor` is skills-only for now.

Pi differs from the other three in *how* it packages the same content: it has no
marketplace file and no built-in MCP support. A pi package is any directory with
a `package.json` carrying a `pi` field, so the **repo-root
[package.json](package.json)** is the manifest (its `pi` field points into
[pi/dev-plugin/](pi/dev-plugin)) and the whole repo installs as one pi package.
The MCP server is surfaced through the community
[`pi-mcp-adapter`](https://pi.dev/packages/pi-mcp-adapter) extension, which pi
loads only as a package in its own right — so it is installed alongside this one,
not pulled in by it. See [pi/README.md](pi/README.md).

---

# Development and maintenance

Everything below is for people working **on** the plugins rather than with them.

| Harness | Plugin Folder | Test suite | CI workflow |
| ------- | ------------- | ---------- | ----------- |
| [Claude Code](https://claude.com/claude-code) | [`claude`](claude) | [`claude/dev-plugin-tests`](claude/dev-plugin-tests) | [claude-test.yml](.github/workflows/claude-test.yml) |
| [Codex](https://openai.com/codex) | [`codex`](codex) | [`codex/dev-plugin-test`](codex/dev-plugin-test) | [codex-test.yml](.github/workflows/codex-test.yml) |
| [OpenCode](https://opencode.ai) | [`opencode`](opencode) | [`opencode/dev-plugin-test`](opencode/dev-plugin-test) | [opencode-test.yml](.github/workflows/opencode-test.yml) |
| [Pi](https://pi.dev) | [`pi`](pi) | [`pi/dev-plugin-tests`](pi/dev-plugin-tests) | [pi-test.yml](.github/workflows/pi-test.yml) |

## How the plugins are built

1. **Skills** — MariaDB agent skills (`SKILL.md` docs) covering SQL statements,
   functions, client tools, connectors, and topical deep-dives. Most are vendored
   from
   [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills);
   additional repo-local skills are maintained in
   [additional-skills/](additional-skills), grouped into `sql/` (e.g.
   `mariadb-schema-create-script`), `rest/` (MariaDB REST Service) and
   `schema-management/` (MSM lifecycle) subfolders. The `dev` plugin vendors all
   of them; the `sql` plugin vendors only `additional-skills/sql/`. The agent
   surfaces the right skill by its `description` "Use when …" trigger.
2. **A native MCP server** — the [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
   binary, launched by [scripts/mariadb-mcp-launcher.sh](claude/dev-plugin/scripts/mariadb-mcp-launcher.sh)
   (and `.cmd` for native Windows). On first use it runs the first
   `mariadb-shell` that satisfies `MARIADB_SHELL_VERSION` — `$MARIADB_SHELL_BIN`,
   one on `PATH`, or an install in `~/.local/bin`
   (`%LOCALAPPDATA%\Programs\mariadb-shell\bin` on Windows) — and otherwise runs
   the shell's own `install.sh` / `install.ps1` to put the newest release there
   first. Either way it execs that binary as the MCP server over stdio, and later
   runs reuse the install. Pi uses the same launcher, registered with
   `pi-mcp-adapter` by
   [pi/dev-plugin/scripts/setup-pi-mcp.sh](pi/dev-plugin/scripts/setup-pi-mcp.sh).

## Repository layout

```text
ai-plugins/
├── .claude-plugin/marketplace.json    # Claude Code marketplace entry
├── .agents/plugins/marketplace.json   # Codex marketplace entry (Codex reads this, not .codex-plugin/)
├── additional-skills/                 # repo-local skills, grouped by topic subfolder
│   ├── sql/                            # vendored into dev + sql (e.g. mariadb-schema-create-script)
│   ├── rest/                           # MariaDB REST Service skills (dev only)
│   └── schema-management/              # MSM lifecycle skills (dev only)
├── claude/
│   ├── dev-plugin/                    # the Claude Code plugin (skills/, scripts/, .mcp.json)
│   ├── sql-plugin/                    # SQL-focused variant (no client-tool/connector skills)
│   ├── contributor-plugin/           # mariadb-shell contributor skills (skills only)
│   └── dev-plugin-tests/              # its pytest suite (4 tiers — adds e2e)
├── codex/
│   ├── dev-plugin/
│   ├── sql-plugin/
│   ├── contributor-plugin/
│   └── dev-plugin-test/
├── opencode/
│   ├── dev-plugin/
│   ├── sql-plugin/
│   ├── contributor-plugin/
│   └── dev-plugin-test/
├── pi/                                # Pi (pi.dev) extension sources — dev only for now
│   ├── dev-plugin/                    # src/index.ts extension, scripts/ (setup-pi-mcp + launchers), skills/
│   └── dev-plugin-tests/              # its pytest suite (static + db + e2e; no eval tier)
├── package.json                       # repo-root pi manifest (`pi` field → pi/dev-plugin/); pi-mcp-adapter dep + test scripts
├── run_tests.py                        # runs every suite with the mariadb-shell Python + coverage
├── pytest-coverage.ini                 # shared pytest config used by run_tests.py
├── .coveragerc                         # coverage config (reports in test-results/ + htmlcov/)
├── scripts/
│   └── sync-skills.sh                 # vendors skills into every plugin
└── .github/workflows/                 # one CI workflow per harness (pi has no eval job)
```

## Skills sync

Skills are **vendored** into each plugin — the plugins are self-contained and are
never edited by hand. [scripts/sync-skills.sh](scripts/sync-skills.sh) is the
single source of truth:

```sh
scripts/sync-skills.sh          # sync the latest upstream (default branch head)
scripts/sync-skills.sh <ref>    # or a specific tag / branch / commit
```

It downloads the upstream `agent-skills/` tree once at the chosen ref — the
latest commit on the upstream default branch unless you pass one — and copies the
selected skills into each `dev`/`sql` plugin's `skills/` dir, writing per-plugin
provenance (including the exact commit SHA synced) to `skills-source.json`. The `dev` plugins get every upstream layer
plus all `additional-skills/` subfolders; the `sql` plugins get the SQL-focused
upstream layers plus only `additional-skills/sql/` (`rest/` and
`schema-management/` are dev-only — see `SQL_INCLUDE_LAYERS` in the script). It
also vendors the
`contributor` plugins from a separate source — the `mariadb-shell` repo's
`.claude/skills/` tree; since that repo is private, this step needs `GH_TOKEN`
(or `gh auth token`) and is skipped with a warning when no credentials are present.

**Flat layout.** Every plugin — including `pi/dev-plugin` — vendors skills flat,
`skills/<skill>/SKILL.md`, regardless of how they are grouped upstream. This is
what OpenCode requires (it discovers skills only one directory deep) and it keeps
every plugin identical on disk. It also keeps pi's loader happy: `skills/` must
contain nothing but skill directories plus the manifest and
`skills-source.json` — a stray dir without a `SKILL.md` makes pi's loader fail. The vendored `.skills-manifest.json` is rewritten to flat paths while
preserving each skill's layer grouping, so the manifest-driven test suites still
resolve. Requires `jq` and `curl`.

## Testing

All four harness plugins have a parallel pytest suite;
[run_tests.py](run_tests.py) discovers them by `*/dev-plugin-test*/conftest.py`:

| Tier | Marker | Needs | Checks |
| ---- | ------ | ----- | ------ |
| 1. Static / structural | `static` | nothing | frontmatter, manifest↔disk consistency, cross-references, SQL fences, statement-skill contract |
| 2. SQL execution | `db` | `mariadb-shell` + a server binary | the skills' recommended DDL runs on a live server with the documented effect |
| 3. Behavioral evals | `eval` | an LLM API key | the skill steers the model toward the MariaDB-preferred form (opt-in; deselected by default) |
| 4. End-to-end | `e2e` | the harness CLI, authenticated | drives the real CLI with the plugin loaded, then asserts the side effects (opt-in) |

Tiers 1 and 2 are the same everywhere. The opt-in tiers differ by harness,
because what there is to drive differs:

- **Claude** — `eval` (Anthropic SDK) plus two `e2e` modules: the REST workflow
  (sandbox, schema, REST DDL) and the MSM schema-lifecycle workflow.
- **Codex** — `eval` (OpenAI SDK) plus the same two `e2e` workflows, and two
  token-free checks that Codex resolves this repo's *Codex* plugin and that
  `setup-codex-mcp.sh` registers a server it can actually spawn.
- **OpenCode** — `eval` only; no `e2e` yet.
- **Pi** — `e2e` only, and **no `eval` tier**: pi has no SDK of its own to prompt,
  so driving the `pi` binary *is* the behavioural test. Its e2e installs this repo
  as a project-local pi package (`pi install -l`, which pi honours only when the
  run passes `--approve`), checks that the vendored skills reached the model and
  that the generated schema script carries the Start Block its skill mandates, and
  verifies `setup-pi-mcp.sh` registers the MariaDB server with `pi-mcp-adapter`
  idempotently. There are no MCP tool-call assertions: pi has no built-in MCP, and
  the adapter that provides it is installed separately from this package.

The `e2e` tiers self-skip rather than fail when their toolchain is absent — no
CLI, no authenticated provider, or no resolvable `mariadb-shell`.

The `db` tier needs no server running beforehand: it deploys a throwaway
**sandbox instance** on a free port through the `mariadb-shell` MCP server's
`sandbox.*` tools, the way `mariadb-shell-plugins/mcp_plugin/tests` does, and
deletes it afterwards. The shell's user config home is isolated to a temp dir for
the run (with the real one's plugins symlinked in, and the sandbox dir
allow-listed), so nothing touches `~/.mariadb-shell`. Setting any of
`MARIADB_HOST` / `MARIADB_PORT` / `MARIADB_USER` / `MARIADB_PASSWORD` switches the
tier onto that already-running server instead — which is what CI and
`docker-compose.yml` do. `MARIADB_SANDBOX_MARIADBD` pins the server binary the
sandbox starts. The tier skips only when no sandbox can be deployed at all (no
`mariadb-shell`, no `mariadbd`/`mysqld`, or an MCP server without the sandbox
tools).

### The unified runner

[run_tests.py](run_tests.py) runs every suite with **the Python that ships inside
`mariadb-shell`** (`mariadb-shell --pym pytest`), the same way
`mysql-shell-plugins/mcp_plugin/run_tests.py` does, so the tests execute against
the same interpreter and packages as the MCP server they exercise. It installs
each suite's `requirements.txt` into that Python, runs one pytest process per
suite (their same-named modules and `lib` packages can't share a process), and
appends coverage across the runs into one combined report.

```sh
./run_tests.py                  # every suite, default tiers (static + db)
./run_tests.py claude           # one suite (named after its top-level dir)
./run_tests.py -m static        # a single tier, all suites
./run_tests.py claude -m e2e    # the opt-in end-to-end tier
./run_tests.py -k manifest      # only tests matching a pattern
./run_tests.py -- --lf -x       # anything after `--` is passed to pytest

npm test                        # same, via package.json (also test:static/db/eval/e2e)
```

The binary comes from `--shell`, else `$MARIADB_SHELL`, else `PATH`, and its
directory is prepended to the PATH the suites see so the e2e tier's MCP launcher
resolves the same one. `--no-install` skips the dependency install,
`--no-coverage` the measurement, `--userhome` relocates the shell's user config
home (by default the real one is left alone — the e2e tests that need isolation
create their own).

Config lives in [pytest-coverage.ini](pytest-coverage.ini) (markers, default tier
selection, report formats) and [.coveragerc](.coveragerc). Reports land in
`test-results/` (`coverage.xml`, `<suite>-tests.xml`) and `htmlcov/`, all
git-ignored. Coverage measures the suites' own Python — the `lib/` helpers and
`conftest.py` fixtures; the skills themselves are Markdown, which the static tier
checks instead.

### Per-suite, without the runner

```sh
cd claude/dev-plugin-tests      # or pi/dev-plugin-tests , codex/ , opencode/ dev-plugin-test
pip install -r requirements.txt
pytest -m static                # fast, no services
pytest -m db                    # needs a MariaDB 11.8 server (docker-compose.yml provided)
pytest -m eval                  # opt-in, calls the LLM API      (not in the pi suite)
pytest -m e2e                   # opt-in, drives the harness CLI (claude, codex, pi)
```

The eval tier uses the SDK matching its agent: the Claude and OpenCode suites call
the Anthropic SDK (`claude-opus-4-8`, needs `ANTHROPIC_API_KEY`); the Codex suite
calls the OpenAI SDK. The pi suite has no eval tier at all — see the tier notes
above. CI runs `static` on every push/PR and `db` on PRs for all four suites, and `eval`
nightly / on demand for the three that have it; the `e2e` tiers are local-only,
since they need an authenticated CLI and a `mariadb-shell` on the machine.

## License

Plugin code largely depends on the MariaDB Shell MCP plugin and is therefore
licensed under **GPL-2.0** — see [LICENSE](LICENSE); each plugin ships an
identical copy.

The bundled skills are vendored from several source repositories and retain their
original licenses. The topical layer, for instance, carries its own `LICENSE` and
`VENDORED.md` upstream in
[`mariadb-corporation/mariadb-docs/agent-skills/topical`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills/topical).
See [additional-skills/README.md](additional-skills/README.md) for the full list
of sources and their licensing.
