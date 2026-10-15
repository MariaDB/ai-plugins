# MariaDB SQL plugin for Hermes Agent

Version **26.10.3**

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
otherwise installs the newest release there with the shell's own installer. Then
it starts that binary as the MCP server. Later runs reuse the install.

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
      "env": { "MARIADB_SHELL_VERSION": "26.10.1" }
    }
  }
}
```

Hermes resolves the `./` command against the installed plugin folder and runs it
without a shell. The server's tools reach the model as `mcp__mariadb__<tool>`,
for example `mcp__mariadb__db_list_connections`.

The launcher ([scripts/mariadb-mcp-launcher.sh](scripts/mariadb-mcp-launcher.sh)):

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

**Windows:** `mcp.json` cannot branch per OS, and the `.sh` launcher needs a
POSIX shell. On native Windows, add a server of the same name to your Hermes
`config.yaml`; a `config.yaml` server replaces the plugin's entry of that name:

```yaml
mcp_servers:
  mariadb:
    command: "C:\\Users\\<you>\\AppData\\Local\\hermes\\plugins\\mariadb-sql\\scripts\\mariadb-mcp-launcher.cmd"
    args: []
```

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
