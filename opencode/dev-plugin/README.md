# MariaDB plugin for OpenCode

Version **26.10.4**

This plugin gives [OpenCode](https://opencode.ai) first-class MariaDB support
through two parts:

1. **Skills** — MariaDB agent skills (SQL statements, functions, client tools,
   and topical deep-dives) vendored from
   [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills),
   baseline **MariaDB 11.8 LTS**. They follow the open `SKILL.md` standard, so
   OpenCode loads them contextually and you can invoke them via `/skills`.
2. **A native MCP server** — the [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
   binary, started automatically by a launcher that finds a suitable install or,
   failing that, runs the shell's own installer to get one.

## Installation

OpenCode has no central plugin marketplace; you wire the two parts into your
OpenCode config and skills directories. Clone this repo (or copy this
`dev-plugin/` directory) somewhere stable, then:

**1. Register the MCP server.** Merge the `mcp` block from this plugin's
[opencode.json](opencode.json) into your project `opencode.json` (or global
`~/.config/opencode/opencode.json`), and point `MARIADB_DEV_PLUGIN` at this
directory:

```sh
export MARIADB_DEV_PLUGIN=/path/to/ai-plugins/opencode/dev-plugin
```

On Windows, write the path with forward slashes, for example
`setx MARIADB_DEV_PLUGIN C:/path/to/ai-plugins/opencode/dev-plugin`. OpenCode pastes the
value into the JSON text before parsing it, and backslashes there make the
whole config invalid (`InvalidEscapeCharacter`).

**2. Make the skills discoverable.** OpenCode loads skills one directory deep from
`.opencode/skills/`, `~/.config/opencode/skills/`, `.claude/skills/`, and
`.agents/skills/`. Symlink (or copy) the flat `skills/` dir into one of those:

```sh
ln -s "$MARIADB_DEV_PLUGIN/skills" ~/.config/opencode/skills/mariadb
# …or per-project:
ln -s "$MARIADB_DEV_PLUGIN/skills" .opencode/skills/mariadb
```

On first use of a MariaDB tool, the launcher looks for a `mariadb-shell` it can
run — `$MARIADB_SHELL_BIN`, one on `PATH`, or an existing install in
`~/.local/bin` (`%LOCALAPPDATA%\Programs\mariadb-shell\bin` on Windows) — and
otherwise installs the newest release there with the shell's own installer. Then
it starts that binary as the MCP server. Later runs reuse the install.

## The MCP server

Configured in [opencode.json](opencode.json):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "mariadb": {
      "type": "local",
      "command": ["{env:MARIADB_DEV_PLUGIN}/scripts/mariadb-mcp-launcher"],
      "environment": { "MARIADB_SHELL_VERSION": "26.10.3" },
      "enabled": true
    }
  }
}
```

OpenCode substitutes `{env:MARIADB_DEV_PLUGIN}` from the environment (its documented
variable-substitution syntax), so the launcher resolves regardless of where OpenCode
is started.

The launcher ([scripts/mariadb-mcp-launcher.sh](scripts/mariadb-mcp-launcher.sh)):

- Resolves the minimum version from `MARIADB_SHELL_VERSION` (default `26.10.3`).
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

**Windows:** `opencode.json` cannot branch per OS, so it names the extensionless
launchers `scripts/mariadb-mcp-launcher` and `scripts/mariadb-lsp-launcher`. On
macOS and Linux each is a shell script that hands over to its `.sh` twin; on
native Windows, OpenCode resolves the name through `%PATHEXT%` and runs the
`.cmd` launcher next to it, so no edit is needed.

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

This plugin enforces that with an OpenCode plugin,
[plugins/mariadb-guard.ts](plugins/mariadb-guard.ts), which blocks such a bash
call and adds the rule to the system prompt. The `plugin` entry in
[opencode.json](opencode.json) loads it; merge it along with the `mcp` block.

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

## The SQL language server

`mariadb-lsp`, the MariaDB SQL language server, ships in the `mariadb-shell`
packages from 26.10.3 on. OpenCode feeds its diagnostics back to the model after
each edit of a `.sql` file. Configured in [opencode.json](opencode.json), next to
the MCP server:

```json
{
  "lsp": {
    "mariadb": {
      "command": ["{env:MARIADB_DEV_PLUGIN}/scripts/mariadb-lsp-launcher"],
      "extensions": [".sql"],
      "env": { "MARIADB_SHELL_VERSION": "26.10.3" }
    }
  }
}
```

OpenCode leaves every language server off while `lsp` is missing from its
config. This entry turns them on: its own built-in servers as well as this one.
To keep them off, leave the `lsp` key out of what you merge into your config.

OpenCode gives a language server 45 seconds to start, a limit it has no setting
for, and skips a server that misses it for the rest of the session. On a first
start the language server waits for the MCP launcher to download mariadb-shell;
if that takes longer, restart OpenCode once the download is done.

The launcher ([scripts/mariadb-lsp-launcher.sh](scripts/mariadb-lsp-launcher.sh))
**never installs anything**. Installing `mariadb-shell` is left to the MCP launcher
alone, so starting both servers at once downloads the package once. It:

- Finds the `mariadb-shell` the MCP launcher would run (`$MARIADB_SHELL_BIN`, one
  on `PATH`, or `~/.local/bin/mariadb-shell`, at `MARIADB_SHELL_VERSION` or newer)
  and starts the `mariadb-lsp` packaged with it, as `mariadb-lsp lsp`.
- When there is no such shell yet, as on a first start, waits for the MCP
  launcher's install (`MARIADB_LSP_WAIT` seconds, default 180), then looks again.
- Falls back to any `mariadb-lsp` on `PATH` or in `~/.local/bin`. The native
  `.deb` and `.rpm` packages of the shell do not include it yet.
- Takes `MARIADB_LSP_BIN` to run a binary of your own instead.

## Skills

Skills are vendored under [skills/](skills/) in a **flat** layout — one directory
per skill, directly under `skills/` — because OpenCode discovers skills only one
directory deep. They are kept in sync across all plugins by the repo-wide updater
[scripts/sync-skills.sh](../../scripts/sync-skills.sh) (which flattens this target
automatically) — to refresh from upstream, run it from the repo root (it syncs
the latest upstream by default; pass a ref to sync a specific version); per-plugin
provenance is recorded in [skills-source.json](skills-source.json).

```text
skills/
├── statements   create-table, alter-table, select, insert, update, delete,
│                replace, create-view, create-index, drop-table,
│                create-database, load-data
├── functions    json, string, date-time, numeric, aggregate
├── tools        dump, import
└── topical      features, query-optimization, system-versioned-tables,
                 mysql-to-mariadb, vector
```

## License

Plugin code is **GPL-2.0** — see [LICENSE](LICENSE). The bundled skills are
vendored from several source repositories and retain their original licenses;
see [additional-skills/README.md](../../additional-skills/README.md) for the full list of sources and their
licensing.
