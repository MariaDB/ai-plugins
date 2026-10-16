# MariaDB plugin for Codex

Version **26.10.3**

This plugin gives [OpenAI Codex](https://developers.openai.com/codex/) first-class
MariaDB support through two parts:

1. **Skills** — MariaDB agent skills (SQL statements, functions, client tools,
   and topical deep-dives) vendored from
   [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills),
   baseline **MariaDB 11.8 LTS**. They follow the open
   [agent-skills](https://developers.openai.com/codex/skills) standard (`SKILL.md`),
   so Codex loads them contextually and can invoke them via `/skills` or `$`.
2. **A native MCP server** — the [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
   binary, started automatically by a launcher that finds a suitable install or,
   failing that, runs the shell's own installer to get one.

## Installation

```sh
codex plugin marketplace add mariadb/ai-plugins
codex plugin add dev@mariadb
```

That is the whole installation: the plugin declares its MCP server in a shape
Codex can actually spawn (see below), so there is no second step. If the server
does not come up, [scripts/setup-codex-mcp.sh](scripts/setup-codex-mcp.sh) — or
[.cmd](scripts/setup-codex-mcp.cmd) on native Windows — registers it explicitly
as a fallback:

```sh
codex/dev-plugin/scripts/setup-codex-mcp.sh     # --remove to unregister
```

Codex's `/plugins` slash command browses and enables plugins interactively; it
takes no arguments, so adding a marketplace is done with the CLI above. On first
use of a MariaDB tool, the launcher looks for a `mariadb-shell` it can run —
`$MARIADB_SHELL_BIN`, one on `PATH`, or an existing install in `~/.local/bin`
(`%LOCALAPPDATA%\Programs\mariadb-shell\bin` on Windows) — and otherwise installs
the newest release there with the shell's own installer. Then it starts that
binary as the MCP server. Later runs reuse the install.

## The MCP server

Declared in [.mcp.json](.mcp.json):

```json
{
  "mcpServers": {
    "mariadb": {
      "command": "./scripts/mariadb-mcp-launcher",
      "cwd": ".",
      "args": [],
      "env": { "MARIADB_SHELL_VERSION": "26.10.1" }
    }
  }
}
```

Three details in there are each load-bearing, and getting any of them wrong
registers a server that silently never starts:

- **`mcpServers`, camelCase** — the only key Codex reads. A `mcp_servers` key
  registers nothing at all, without a word of complaint.
- **A relative `command`, with no `${...}` placeholder.** Codex expands none of
  them when it spawns a plugin's server; it execs the stored command verbatim.
  There is no `${CODEX_PLUGIN_ROOT}`, and `${CLAUDE_PLUGIN_ROOT}` — the one name
  Codex recognises elsewhere — is not expanded on this path either. Either way
  the server dies with `MCP startup failed: No such file or directory`.
- **`"cwd": "."`** — this is what Codex *does* resolve to the plugin's install
  directory, and it is what the relative command is then resolved from. Without
  it the command resolves from your own working directory instead.

**One command name, every OS.** `command` names
[scripts/mariadb-mcp-launcher](scripts/mariadb-mcp-launcher) — deliberately
without an extension, because `.mcp.json` cannot branch per OS and Windows cannot
execute a `.sh`. Codex resolves the program per platform: on macOS and Linux it
hands the name to the OS unchanged and the kernel runs that file through its
shebang, while on Windows it resolves through `%PATHEXT%` and lands on
[scripts/mariadb-mcp-launcher.cmd](scripts/mariadb-mcp-launcher.cmd) instead, the
extensionless file being skipped there as not a Windows binary. It is the same
mechanism that lets `npx` and `pnpm` work in a Codex MCP entry. The extensionless
file is a three-line shim, so that `mariadb-mcp-launcher.sh` keeps the name it has
in every other plugin in this repo.

If the server still does not start,
[scripts/setup-codex-mcp.sh](scripts/setup-codex-mcp.sh) (or
[.cmd](scripts/setup-codex-mcp.cmd) on native Windows) is the fallback: it runs
`codex mcp add`, writing an `[mcp_servers.mariadb]` entry into
`$CODEX_HOME/config.toml` with the absolute path resolved on your machine, and
that entry takes precedence over the plugin's.

The real launcher ([scripts/mariadb-mcp-launcher.sh](scripts/mariadb-mcp-launcher.sh)), which the shim execs:

- Resolves the minimum version from `MARIADB_SHELL_VERSION` (default `26.10.1`).
- Runs the first `mariadb-shell` that meets it: `$MARIADB_SHELL_BIN`, then one on
  `PATH`, then a local install at `~/.local/bin/mariadb-shell`
  (`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd` on Windows).
- Failing all three, runs the shell's own installer — `install.sh`, or
  `install.ps1` on Windows, fetched from
  `raw.githubusercontent.com/mariadb-corporation/mariadb-shell/main/`. It picks
  the package matching this OS, CPU and glibc version, verifies it against the
  release's `SHA256SUMS`, unpacks it under `~/.local/share/mariadb-shell/` and
  links the binary into `~/.local/bin`. Later starts reuse that install.
- Execs whichever binary it settled on as
  `mariadb-shell -- mcp start-server --transport=stdio`. stdout belongs to the
  MCP transport alone, so the launcher's own messages — and the installer's — go
  to stderr.

**Private repository:** while `mariadb-shell` is private, set `GH_TOKEN` (or
`MARIADB_SHELL_TOKEN`, or simply run `gh auth login`). The token is needed twice:
to fetch the installer, and for the installer to download the release.

**Prereleases:** nothing to set. The installer skips prereleases, as
`releases/latest` does, so the launcher tries a stable release first and retries
with `--pre-release` when there is none — which is the case until a stable
`mariadb-shell` is published. `MARIADB_SHELL_PRERELEASE=1` skips straight to a
prerelease; `=0` refuses one and keeps the install stable-only.

### Configure what the server may access

The skills work on their own. The MCP server, however, starts out allowed to reach
nothing — installing this plugin wires it up, but does not tell it what it may
touch. Run this once per machine:

```sh
mariadb-shell -- mcp setup     # or mcp.setup() from an interactive shell
```

If `mariadb-shell` isn't on your `PATH`, use the copy the launcher installed —
`~/.local/bin/mariadb-shell`, or
`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd` on Windows. The
installer only prints a `PATH` hint; it never edits your shell profile. That copy
appears the first time this plugin starts the MCP server, so either let the agent
run once first, or install the shell yourself before configuring it.

### Database access goes through the MCP server

The agent uses the MCP server's tools, not a command-line client, for anything
those tools do. A client run from the agent's shell needs the password on its
command line (`-p<password>`) or in its environment. From there it reaches the
process list, logs, and the conversation the model provider sees. A connection
opened through the MCP server reads its password from the secret store, so the
agent never sees one. To give the agent a server, configure it yourself with
`mariadb-shell -- mcp setup` (see above) or its
[command-line options](https://mariadb.com/docs/tools/community/mariadb-shell/mcp-server/automated-setup).
For a local test server the agent deploys a sandbox, with a random root
password it generates; the password is stored with the sandbox's connection.

This plugin enforces that with a `PreToolUse` hook on the shell tool
([hooks/hooks.json](hooks/hooks.json), [hooks/mariadb-cli-guard.sh](hooks/mariadb-cli-guard.sh)).
**Codex runs a plugin's hooks only once you have trusted them.** Start an
interactive `codex` session after installing; it asks you to review the new
hooks, and approving them is a one-time step. Until then Codex skips the hook
without a word, and `codex exec` never asks.

It looks at only five clients, and each only where an MCP tool does the job:

| Client | Blocked when | Use instead |
| --- | --- | --- |
| `mariadb`, `mysql` | it runs SQL | `db.execute_sql`, `db.execute_sql_script` |
| `mariadb-shell`, `mysqlsh` | it runs SQL (SQL mode) | `db.execute_sql`, `db.execute_sql_script` |
| `mariadb-shell`, `mysqlsh` | it calls `-- <object> <method>` that a tool wraps, such as `-- util dump-schemas` | the matching tool, here `util.dump_schemas` |
| `mariadb-dump` | its output is piped into another client | `util.copy_instance`, `util.copy_schemas`, `util.copy_tables` |

Everything else runs: `--version` and `--help`, Python or JavaScript mode, a dump
written to a file, `mariadb-shell -- mcp setup`, an API call no tool wraps, and
every other client. A client is caught behind a path, `env`, a pipe, `&&`,
`sh -c "..."` or `$(...)`. The model is told which tool to use instead. To let
the agent run the clients regardless, start it with `MARIADB_PLUGIN_ALLOW_CLI=1`
in its environment; the model cannot set that itself.

## Skills

Skills are vendored under [skills/](skills/), preserving the upstream layer
layout. They are kept in sync across all plugins by the repo-wide updater
[scripts/sync-skills.sh](../../scripts/sync-skills.sh) — to refresh from upstream,
run it from the repo root (it syncs the latest upstream by default; pass a ref to
sync a specific version); per-plugin provenance is recorded in
[skills-source.json](skills-source.json).

```text
skills/
├── granular/
│   ├── statements/   create-table, alter-table, select, insert, update, delete,
│   │                 replace, create-view, create-index, drop-table,
│   │                 create-database, load-data
│   ├── functions/    json, string, date-time, numeric, aggregate
│   └── tools/        dump, import
└── topical/          features, query-optimization, system-versioned-tables,
                      mysql-to-mariadb, vector
```

## License

Plugin code is **GPL-2.0** — see [LICENSE](LICENSE). The bundled skills are
vendored from several source repositories and retain their original licenses;
see [additional-skills/README.md](../../additional-skills/README.md) for the full list of sources and their
licensing.
