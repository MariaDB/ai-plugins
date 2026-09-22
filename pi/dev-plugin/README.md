# MariaDB plugin for Pi

Version **26.9.3**

This plugin gives the [Pi coding agent](https://pi.dev) first-class MariaDB
support as a **pi extension**, through two parts:

1. **Skills** — MariaDB agent skills (SQL statements, functions, client tools,
   connectors, and topical deep-dives) vendored from
   [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills),
   baseline **MariaDB 11.8 LTS**. They are declared in the package's `pi.skills`
   field, so pi loads them contextually.
2. **A native MCP server** — the [`mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
   binary, started by [scripts/mariadb-mcp-launcher.sh](scripts/mariadb-mcp-launcher.sh),
   surfaced to pi through [`pi-mcp-adapter`](https://pi.dev/packages/pi-mcp-adapter),
   which is installed as its own pi package.

Pi has no bundled MCP support — the community `pi-mcp-adapter` extension is what
connects pi to MCP servers, exposing them through a single token-cheap `mcp`
proxy tool. This plugin depends on it and registers the mariadb-shell server in
its config.

## How it is structured (a pi extension)

The **pi manifest lives at the repository root** (`../../package.json`), so the
whole repo is one installable pi package — `pi install git:…/ai-plugins` works
directly. Its paths point into this directory:

```text
ai-plugins/
├── package.json     # pi manifest: pi.extensions + pi.skills (→ pi/dev-plugin/…); deps incl. pi-mcp-adapter
└── pi/dev-plugin/
    ├── src/index.ts     # the extension (default-export factory): /mariadb-mcp-setup + session hint
    ├── scripts/
    │   ├── setup-pi-mcp.sh          # registers the mariadb server with pi-mcp-adapter
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
  },
  "dependencies": { "pi-mcp-adapter": "^2.15.0" }
}
```

`pi.skills` points at the skills **root** (not `skills/*`): pi discovers every
directory that contains a `SKILL.md` recursively, so only real skills load.

## Installation

**1. Install the MCP adapter** (once, if you don't have it yet):

```sh
pi install npm:pi-mcp-adapter
```

**2. Install this plugin** straight from GitHub:

```sh
pi install git:github.com/mariadb/ai-plugins
# …or from a local checkout of this repo (run at the repo root):
pi install .
```

`pi install` runs `npm install`, so the `pi-mcp-adapter` dependency is pulled in
automatically. Pi discovers the skills and the extension from the root `pi`
manifest field; restart pi (or `/reload`) to load them.

**3. Register the MariaDB MCP server** with the adapter — either the slash
command inside pi:

```text
/mariadb-mcp-setup            # writes the global ~/.config/mcp/mcp.json
/mariadb-mcp-setup --project  # or ./.mcp.json for just this project
```

…or the script directly:

```sh
pi/dev-plugin/scripts/setup-pi-mcp.sh            # global
pi/dev-plugin/scripts/setup-pi-mcp.sh --project  # ./.mcp.json
```

Then `/mcp reconnect mariadb` (or restart pi). The extension also prints a
one-line reminder at session start whenever the server isn't configured yet.

On first use of a MariaDB tool, the launcher looks for a `mariadb-shell` it can
run — `$MARIADB_SHELL_BIN`, one on `PATH`, or an existing install in
`~/.local/bin` (`%LOCALAPPDATA%\Programs\mariadb-shell\bin` on Windows) — and
otherwise installs the newest release there with the shell's own installer. Then
it starts that binary as the MCP server. Later runs reuse the install. Set
`GH_TOKEN` (or run `gh auth login`) while `mariadb-shell` is private; the release
channel needs no setting, as the launcher falls back to a prerelease while no
stable `mariadb-shell` is published.

## The MCP server entry

`setup-pi-mcp.sh` merges this into the adapter's `mcp.json` (preserving anything
else already there):

```json
{
  "mcpServers": {
    "mariadb": {
      "command": "<plugin>/scripts/mariadb-mcp-launcher.sh",
      "args": [],
      "env": { "MARIADB_SHELL_VERSION": "26.9.3" },
      "lifecycle": "lazy"
    }
  }
}
```

`lifecycle: "lazy"` tells the adapter to spawn mariadb-shell only when a MariaDB
tool is first used.

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
