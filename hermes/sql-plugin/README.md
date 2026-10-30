# MariaDB SQL plugin for Hermes Agent

Version **26.10.6**

This plugin gives [Hermes Agent](https://hermes-agent.nousresearch.com/) first-class
MariaDB SQL support through two parts:

1. **Skills** — MariaDB agent skills (SQL statements, functions, and topical
   deep-dives) vendored from
   [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills),
   baseline **MariaDB 11.8 LTS**.
2. **A native MCP server** — the [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
   binary, started automatically by a launcher that finds a suitable install or,
   failing that, runs the shell's own installer to get one.

It is a portable **Agent Plugins v1** package: a root [plugin.json](plugin.json),
a [skills/](skills/) directory and a root [mcp.json](mcp.json). Hermes loads it
without any Python code of its own.

## Installation

```sh
hermes plugins install mariadb/ai-plugins#hermes/sql-plugin --enable
```

Then start a new Hermes session; MCP servers connect at session start.

- `#hermes/sql-plugin` installs this folder of the repository, not the whole repo.
- `--enable` is needed because Hermes installs portable packages **disabled**.
  Without it, run `hermes plugins enable mariadb-sql` afterwards.

To update later, run `hermes plugins update mariadb-sql`; to remove it,
`hermes plugins remove mariadb-sql`.

On first use of a MariaDB tool, the launcher looks for a `mariadb-shell` it can
run — `$MARIADB_SHELL_BIN`, one on `PATH`, or an existing install in
`~/.local/bin` (`%LOCALAPPDATA%\Programs\mariadb-shell\bin` on Windows) — and
otherwise installs the `mariadb-shell` release this plugin was tested with there,
using the shell's own installer. Then it starts that binary as the MCP server.
Later runs reuse the install.

## The MCP server

Configured in [mcp.json](mcp.json):

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "mariadb": {
      "type": "stdio",
      "command": "./scripts/mariadb-mcp-launcher.sh",
      "args": [],
      "env": { "MARIADB_SHELL_VERSION": "26.10.4" }
    }
  }
}
```

Hermes resolves the `./` command against the installed plugin folder and runs it
without a shell. The server's tools reach the model as `mcp__mariadb__<tool>`,
for example `mcp__mariadb__db_list_connections`.

The launcher ([scripts/mariadb-mcp-launcher.sh](scripts/mariadb-mcp-launcher.sh)):

- Resolves the minimum version from `MARIADB_SHELL_VERSION` (default `26.10.4`).
- Runs the first `mariadb-shell` that meets it: `$MARIADB_SHELL_BIN`, then one on
  `PATH`, then a local install at `~/.local/bin/mariadb-shell`
  (`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd` on Windows).
- Failing all three, installs release `v$MARIADB_SHELL_VERSION` with the
  shell's own installer — `install.sh`, or `install.ps1` on Windows, fetched from
  a fixed mariadb-shell commit rather than `main`. It picks the package matching
  this OS, CPU and glibc version and verifies it against
  [`scripts/mariadb-shell-v26.10.4.SHA256SUMS`](scripts/mariadb-shell-v26.10.4.SHA256SUMS),
  a copy of that release's checksums kept in this repository, so a package
  replaced on the release afterwards is refused. It unpacks under
  `~/.local/share/mariadb-shell/` and links the binary into `~/.local/bin`.
  Later starts reuse that install.
- Sends no credentials and reads none: `mariadb-shell` is public.
- Execs whichever binary it settled on as
  `mariadb-shell -- mcp start-server --transport=stdio`. stdout belongs to the
  MCP transport alone, so the launcher's own messages — and the installer's — go
  to stderr.

**Windows:** `mcp.json` cannot branch per OS, and the `.sh` launcher needs a
POSIX shell. On native Windows, add a server of the same name to your Hermes
`config.yaml`; a `config.yaml` server replaces the plugin's entry of that name:

```yaml
mcp_servers:
  mariadb:
    command: "C:\\Users\\<you>\\AppData\\Local\\hermes\\plugins\\mariadb-sql\\scripts\\mariadb-mcp-launcher.cmd"
    args: []
```

**Another release:** a newer `mariadb-shell` you install yourself, on `PATH` or
in `~/.local/bin`, is used as it is. To have the launcher install a different
release, set `MARIADB_SHELL_TAG` (for example `v26.10.5`) in the server's `env`;
a release this plugin carries no checksums for is verified against its own
published `SHA256SUMS`, and the launcher says so. Unlike the other harnesses'
plugins, which install the newest release, this one moves to a newer
`mariadb-shell` only with a plugin release.

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

Hermes runs hooks only from a Python plugin, and a Python plugin cannot also
carry skills and an MCP server. So the hook that enforces this is a package of
its own, [`mariadb-guard`](../guard-plugin/README.md). Install it next to this
one:

```sh
hermes plugins install mariadb/ai-plugins#hermes/guard-plugin --enable
```

The guard looks at only five clients, and each only where an MCP tool does the job:

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
packages from 26.10.3 on. Hermes reports its diagnostics in the result of each
`write_file` or `patch` of a `.sql` file. A Hermes plugin cannot register a
language server, so add it to `~/.hermes/config.yaml` yourself. The launcher is
in the installed plugin:

```yaml
lsp:
  warmup_timeout: 240   # room for the first start, see below (default 0)
  servers:
    mariadb:
      command: ["~/.hermes/plugins/mariadb-sql/scripts/mariadb-lsp-launcher.sh"]
      extensions: [".sql"]
      language_id: "sql"
      env: { "MARIADB_SHELL_VERSION": "26.10.4" }
```

Hermes runs language servers only in git repositories, and custom ones only in
trusted workspaces: the worktree you started Hermes in, or one listed under
`lsp.trusted_workspaces`.

On a first start, the language server waits for the MCP launcher to download
mariadb-shell. Without `warmup_timeout`, Hermes gives it 5 seconds
(`wait_timeout`), and a server that misses that budget is skipped for the rest of
the session.

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

Hermes lists plugin skills through its `skills_list` and `skill_view` tools under
a namespace it derives from the plugin, such as
`agent-plugin-mariadb-sql-<hash>:mariadb-create-table`. They are read-only.

Skills are vendored flat under [skills/](skills/), one directory per skill. They
are kept in sync across all plugins by the repo-wide updater
[scripts/sync-skills.sh](../../scripts/sync-skills.sh) — to refresh from upstream,
run it from the repo root (it syncs the latest upstream by default; pass a ref to
sync a specific version); per-plugin provenance is recorded in
[skills-source.json](skills-source.json).

## License

Plugin code is **GPL-2.0** — see [LICENSE](LICENSE). The bundled skills are
vendored from several source repositories and retain their original licenses;
see [additional-skills/README.md](../../additional-skills/README.md) for the full list of sources and their
licensing.
