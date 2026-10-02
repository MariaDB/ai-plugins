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
  server runs inside it as a plugin, using its ability to securely store all
  database credentials. You can also use it yourself as a SQL client —
  run `mariadb-shell` and type `\help`.

> **New to MCP?** The Model Context Protocol is a standardized interface for
> AI agents to call tools — here, the tools that talk to MariaDB.

Works with [Claude Code](https://claude.com/claude-code), [Codex](https://openai.com/codex), [OpenCode](https://opencode.ai) and [Pi](https://pi.dev) — see [Installation](#installation).

> **Prefer a guided start?** The **[DevHub](https://mariadb.github.io/ai-plugins/)**
> has the same installation steps plus hands-on tutorials — building a schema and
> deploying it on a throwaway server, versioned migrations with MSM, REST
> endpoints, and migrating off MySQL. Its source is in [docs/](docs/).

## Installation

The MariaDB AI Plugins use the standard plugin system of the harness where
available.

> Note: On first start, the plugin is going to download and extract the required
> MariaDB Shell package, unless a suitable one is already installed. Depending on
> the network connection speed this might take a bit of time.

### Claude Code

```text
/plugin marketplace add mariadb/ai-plugins
/plugin install dev@mariadb
```

Then configure the MCP server — see
[Configure the MCP server](#configure-the-mcp-server-all-harnesses) below.

### Codex

```sh
codex plugin marketplace add mariadb/ai-plugins
codex plugin add dev@mariadb
```

Codex's `/plugins` slash command browses and enables plugins interactively; it
takes no arguments, so adding a marketplace is done with the CLI above. See
[codex/dev-plugin/README.md](codex/dev-plugin/README.md) for details.

Then configure the MCP server — see
[Configure the MCP server](#configure-the-mcp-server-all-harnesses) below.

### OpenCode

OpenCode has no central marketplace. Merge the `mcp` block from
[opencode/dev-plugin/opencode.json](opencode/dev-plugin/opencode.json) into your
`opencode.json`, point `MARIADB_DEV_PLUGIN` at the plugin dir, and symlink its
flat `skills/` into an OpenCode skills directory. Full steps in
[opencode/dev-plugin/README.md](opencode/dev-plugin/README.md).

Then configure the MCP server — see
[Configure the MCP server](#configure-the-mcp-server-all-harnesses) below.

### Pi

Pi 1.0 or later installs the repo itself as a package (the `pi` field in the
root `package.json`). Its extension registers the MCP server with Pi's built-in
MCP support, so there is no separate setup step:

```sh
pi install git:github.com/mariadb/ai-plugins   # this repo (skills + extension + MCP server)
# …or from a local checkout, at the repo root: pi install .
```

Run `/mcp` in pi to see the `mariadb` server. Coming from an older Pi with
`pi-mcp-adapter`? Remove the adapter first — it replaces the built-in MCP
support. Full steps in [pi/dev-plugin/README.md](pi/dev-plugin/README.md).

That registers the server with pi; configuring what it may access is a separate
step — see [Configure the MCP server](#configure-the-mcp-server-all-harnesses)
below.

## Configure the MCP server (all harnesses)

The skills work on their own. The MCP server, however, starts out allowed to reach
nothing — installing a plugin wires it up, but does not tell it what it may touch.
Run this once per machine:

```sh
mariadb-shell -- mcp setup     # or mcp.setup() from an interactive shell
```

> The MCP server is built as a MariaDB Shell plugin in order to take advantage of
> its high-performance database connections, credential management, sandbox
> handling and advanced database schema management.

If `mariadb-shell` isn't on your `PATH`, use the copy the launcher installed —
`~/.local/bin/mariadb-shell`, or
`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd` on Windows. The
installer only prints a `PATH` hint; it never edits your shell profile. That copy
appears the first time a plugin starts the MCP server, so either let the agent run
once first, or install the shell yourself before configuring it.

The setup configures the following items — see the
[MCP server documentation](https://github.com/mariadb-corporation/mariadb-shell-plugins/blob/main/mcp_plugin/README.md#configuration-mcpsetup)
for the full reference:

- **Connections**: the database connection URIs the LLM will be allowed to
  connect to. Each password is prompted for, verified, and stored in the shell's
  secret store, separately from your regular MariaDB Shell connections. Give each
  one a dedicated MCP account with only the privileges it needs — read-only
  access to certain schemas, say — to keep the LLM from performing potentially
  harmful operations on the database.
- **Allowed paths**: choose the local directories the server may access (the
  current directory is suggested as the default, shown as a full path).
- **Migration tooling** (Linux and macOS only, and offered by the menu on later
  runs rather than by the first-run walkthrough): downloads the
  [MySQL-to-MariaDB migration tooling](https://github.com/mariadb-corporation/Mysql-to-MariaDB-Migration)
  and extracts it into `~/.local/share/mariadb-migrator/<version>`.
  See [Migration tooling](https://github.com/mariadb-corporation/mariadb-shell-plugins/blob/main/mcp_plugin/README.md#migration-tooling).

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

Instances live under `~/.mariadb-shell/sandboxes/<port>/` on macOS and Linux and
under `%USERPROFILE%\MariaDB\mariadb-shell\sandboxes\<port>\` on Windows.

Four things to know regarding sandbox instances:

- **MariaDB Server does not need to be installed.** The sandbox looks for a
  server on the `PATH`, then among the versions it has already downloaded, then
  in its published index — fetching, checksum-verifying and unpacking one if it
  has to. You can also ask for a version (`server_version="11.8"`), and
  `sandbox.list_available_versions` says what is on offer for your platform.
- A database connection to the sandbox is automatically registered with the MCP server.
- The sandbox is deployed without TLS, so command-line clients may need `--skip-ssl`.
- A `root@'%'` account is created and the sandbox listens on all interfaces,
  which is worth changing outside a trusted network.

The MCP server provides 28 tools in three groups:

| Group | Tools | What they do |
| ----- | ----- | ------------ |
| `db.*` | 8 | list connections and schemas, describe objects, run SQL |
| `msm.*` | 12 | MariaDB Schema Management — versioned schema projects, releases, deployments |
| `sandbox.*` | 8 | list deployable server versions; deploy, start, stop and delete local throwaway instances |

## Plugin variants

Each agent ships the plugin variants below — all built by the same
[scripts/sync-skills.sh](scripts/sync-skills.sh):

| Plugin | Skills | MCP server | Skills source |
| ------ | ------ | ---------- | ------------- |
| `dev` | full set — statements, functions, client tools, connectors, topical (+ all local `additional-skills/`: `sql`, `rest`, `schema-management`) | yes | `mariadb-docs` + `additional-skills/` |
| `sql` | SQL-focused subset — statements, functions, topical (+ local `additional-skills/sql`) | yes | `mariadb-docs` + `additional-skills/sql/` |
| `contributor` | skills for **contributing to MariaDB tooling** | no | [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell) `.claude/skills/` |

The folders are `<agent>/{dev,sql,contributor}-plugin/` for each of `claude/`,
`codex/`, and `opencode/`; `pi/` ships `dev` only for now. Skills are baseline
**MariaDB 11.8 LTS**; the `dev` and `sql` plugins share the same auto-downloading
`mariadb-shell` MCP server, while `contributor` is skills-only for now.

Pi differs from the other three in *how* it packages the same content: it has no
marketplace file. A pi package is any directory with
a `package.json` carrying a `pi` field, so the **repo-root
[package.json](package.json)** is the manifest (its `pi` field points into
[pi/dev-plugin/](pi/dev-plugin)) and the whole repo installs as one pi package.
The package's extension registers the MCP server with Pi's built-in MCP support
(Pi 1.0+). See [pi/README.md](pi/README.md).

## Documentation site

[docs/](docs/) holds the **DevHub** — a static Getting Started site served by
GitHub Pages' built-in Jekyll from the `/docs` folder of `main`. It has no build
step and no theme gem.

```sh
gem install jekyll jekyll-seo-tag jekyll-sitemap   # once
npm run docs                                       # → http://127.0.0.1:4000/ai-plugins/
```

See [docs/README.md](docs/README.md) for how to publish it and add a tutorial.
Note that its skill catalog is generated from the vendored manifests — re-run
`npm run docs:skills` after `scripts/sync-skills.sh`.

## Contributing

Working **on** the plugins rather than with them — how they are built, the
repository layout, the skills sync and the test tiers — is covered in
[CONTRIBUTING.md](CONTRIBUTING.md).

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
