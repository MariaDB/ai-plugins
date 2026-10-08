# MariaDB plugin for Pi

Version **26.10.1**

This plugin gives the [Pi coding agent](https://pi.dev) first-class MariaDB
support as a **pi extension**, through two parts:

1. **Skills** — MariaDB agent skills (SQL statements, functions, client tools,
   connectors, and topical deep-dives) vendored from
   [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills),
   baseline **MariaDB 11.8 LTS**. They are declared in the package's `pi.skills`
   field, so pi loads them contextually.
2. **A native MCP server** — the [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
   binary, started by [scripts/mariadb-mcp-launcher.sh](scripts/mariadb-mcp-launcher.sh)
   (or [the `.cmd` launcher](scripts/mariadb-mcp-launcher.cmd) on native Windows).
   The extension registers it with Pi's built-in MCP support as the `mariadb`
   server, so there is nothing to configure.

Requires **Pi 1.0 or later**, the first release with MCP support built in.

## How it is structured (a pi extension)

The **pi manifest lives at the repository root** (`../../package.json`), so the
whole repo is one installable pi package — `pi install git:…/ai-plugins` works
directly. Its paths point into this directory:

```text
ai-plugins/
├── package.json     # pi manifest: pi.extensions + pi.skills (→ pi/dev-plugin/…)
└── pi/dev-plugin/
    ├── src/index.ts     # the extension (default-export factory): registers the mariadb MCP server
    ├── scripts/
    │   ├── mariadb-mcp-launcher.sh  # installs (if needed) + launches mariadb-shell as the MCP server
    │   └── mariadb-mcp-launcher.cmd # native-Windows launcher
    ├── skills/          # vendored MariaDB skills (flat: skills/<skill>/SKILL.md)
    └── skills-source.json
```

The root `package.json` `pi` field is what makes pi treat the repo as a package:

```json
{
  "pi": {
    "extensions": ["./pi/dev-plugin/src/index.ts"],
    "skills": ["./pi/dev-plugin/skills"]
  }
}
```

`pi.skills` points at the skills **root** (not `skills/*`): pi discovers every
directory that contains a `SKILL.md` recursively, so only real skills load.

## Installation

Install this plugin straight from GitHub:

```sh
pi install git:github.com/mariadb/ai-plugins
# …or from a local checkout of this repo (run at the repo root):
pi install .
```

Pi discovers the skills and the extension from the root `pi` manifest field;
restart pi (or `/reload`) to load them. The extension registers the `mariadb`
MCP server as it loads, and Pi connects it when the session starts. Run `/mcp`
in pi to check it: the server is listed with the extension as its source.

On the first connection, the launcher looks for a `mariadb-shell` it can run —
`$MARIADB_SHELL_BIN`, one on `PATH`, or an existing install in `~/.local/bin`
(`%LOCALAPPDATA%\Programs\mariadb-shell\bin` on Windows) — and otherwise installs
the newest release there with the shell's own installer. Then it starts that
binary as the MCP server. Later runs reuse the install.

### How the model reaches the tools

Pi exposes MCP tools through **codemode** by default: the model writes a short
script that calls `tools.mcp__mariadb__db_execute_sql(…)` and the other tools,
and only the script's output enters the context. Pi turns codemode on by itself
once the server connects. To change that, open the server in `/mcp` and pick
another exposure (`direct` declares every tool to the model; `deferred` loads
them through `tool_search`). Pi saves that choice for the current session only,
because the server comes from an extension. To keep it, define the server in
`mcp.json` (next section).

### Overriding the server entry

The registration lives only in the extension. It is not written to any file, so
`pi mcp list` (which loads no extensions) does not show it. A `mariadb` entry in
`~/.pi/agent/mcp.json` or the project's `.pi/mcp.json` takes precedence over the
extension's. Use one to keep an exposure or to give the launcher environment
variables (`--env MARIADB_SHELL_BIN=…`, for example):

```sh
pi mcp add mariadb --exposure direct -- <plugin>/scripts/mariadb-mcp-launcher.sh
```

### Moving from `pi-mcp-adapter`

Earlier versions of this plugin needed the community `pi-mcp-adapter` and a
`/mariadb-mcp-setup` step. Both are gone. The adapter now gets in the way: an
extension that registers `/mcp` replaces Pi's built-in MCP support, so the
`mariadb` server would never connect. To switch over:

```sh
pi remove npm:pi-mcp-adapter
```

Pi 1.0 turns its built-in MCP off when it finds the adapter (it adds
`"-builtin:mcp"` to `extensions` in `~/.pi/agent/settings.json`). Turn it back on
in `pi config` → Built-in → `mcp`, or delete that entry. The old `mariadb` entry
in `~/.config/mcp/mcp.json` (or a project's `.mcp.json`) belonged to the adapter.
Pi does not read it, so you can delete it.

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

Skills are **vendored** — never hand-edited here. They are copied in flat by
[scripts/sync-skills.sh](../../scripts/sync-skills.sh) at the repo root, which is
the single source of truth; see [skills-source.json](skills-source.json) for the
upstream commit that was synced and the skill count.

## License

Plugin code is **GPL-2.0** — see [LICENSE](LICENSE). The bundled skills are
vendored from several source repositories and retain their original licenses;
see [additional-skills/README.md](../../additional-skills/README.md) for the full list of sources and their
licensing.
