---
layout: page
title: Get Started
subtitle: >-
  Install the plugin, tell the MCP server what it may touch, then build a real
  schema on a throwaway server. Fifteen minutes end to end.
badges: ["Claude Code", "Codex", "OpenCode", "Pi"]
permalink: /get-started/
description: Install the MariaDB AI Plugins into Claude Code, Codex, OpenCode or Pi, configure the mariadb-shell MCP server, and run your first working example.
---

There are three steps, and only the first is mandatory. The **skills** work the
moment a plugin loads — no database, no configuration, no network. The **MCP
server** is what turns the agent from a well-informed writer of SQL into
something that can run it.

<div class="callout callout--tip" markdown="1">
**New to MCP?** The Model Context Protocol is a standardized interface that lets
an AI agent call tools. Here, the tools are the ones that talk to MariaDB. You
do not have to understand the protocol to use any of this.
</div>

## Step 1 — Install the plugin
{: #step-1-install-the-plugin}

Pick your harness. Each one ships the same three plugin variants — `dev` (the
full set), `sql` (a SQL-focused subset) and `contributor` (for working on
MariaDB tooling itself). Unless you know you want otherwise, install `dev`.

<div class="callout" markdown="1">
On first start the plugin downloads and extracts the `mariadb-shell` package
unless a suitable one is already installed. Depending on your connection this
can take a minute. It only happens once.
</div>

### Claude Code

```text
/plugin marketplace add {{ site.install_org }}/ai-plugins
/plugin install dev@mariadb
```

### Codex

```sh
codex plugin marketplace add {{ site.install_org }}/ai-plugins
codex plugin add dev@mariadb
```

Codex's `/plugins` slash command browses and enables plugins interactively. It
takes no arguments, so adding the marketplace is done with the CLI above.

### OpenCode

OpenCode has no central marketplace, so the wiring is manual — three small
pieces:

1. Merge the `mcp` block from `opencode/dev-plugin/opencode.json` into your own
   `opencode.json`.
2. Point `MARIADB_DEV_PLUGIN` at the plugin directory.
3. Symlink the plugin's flat `skills/` directory into an OpenCode skills
   directory.

Full steps are in [`opencode/dev-plugin/README.md`]({{ site.repo }}/blob/main/opencode/dev-plugin/README.md).

### Pi

Pi 1.0 or later installs this repository itself as a package — the `pi` field in
the repo-root `package.json` is the manifest. The package's extension registers
the MCP server with Pi's built-in MCP support, so one command does it all:

```sh
pi install git:github.com/{{ site.install_org }}/ai-plugins       # skills + extension + MCP server
# …or from a local checkout, at the repo root:  pi install .
```

Run `/mcp` inside pi to see the `mariadb` server. If you still have
`pi-mcp-adapter` from an older Pi, remove it (`pi remove npm:pi-mcp-adapter`)
and turn the built-in `mcp` back on in `pi config`. The adapter replaces the
built-in MCP support.

### Check that the skills arrived

Ask for something only a skill knows. If the answer uses the native `UUID` type
with `UUID_v7()` rather than `CHAR(36)`, the skills are loaded:

<div class="prompt" markdown="1">
*Write a `CREATE TABLE` for a product catalogue, MariaDB style.*
</div>

## Step 2 — Configure the MCP server
{: #step-2-configure-the-mcp-server}

This is the step people skip, and then wonder why every tool call is refused.

**The server starts out allowed to reach nothing.** Installing a plugin wires
the server up; it does not tell the server what it may touch. Run this once per
machine:

```sh
mariadb-shell -- mcp setup     # or mcp.setup() from an interactive shell
```

If `mariadb-shell` is not on your `PATH`, use the copy the launcher installed —
`~/.local/bin/mariadb-shell`, or
`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd` on Windows. The
installer only prints a `PATH` hint; it never edits your shell profile. That
copy appears the first time an agent starts the MCP server, so either let the
agent run once first, or install the shell yourself before configuring it.

The walkthrough configures three things:

| What | Why it matters |
| --- | --- |
| **Connections** | The database connection URIs the agent is allowed to open. Each password is prompted for, verified, and stored in the shell's secret store — separately from your regular shell connections, and never in a file the agent can read. |
| **Allowed paths** | The local directories the server may read and write. The current directory is offered as the default, shown as a full path. |
| **Migration tooling** | Optional, Linux and macOS only. Downloads the MySQL-to-MariaDB migration tooling into `~/.local/share/mariadb-migrator/<version>`. Offered by the menu on later runs rather than by the first-run walkthrough. |

<div class="callout callout--warn" markdown="1">
**Give each connection its own MariaDB account.** A connection configured here
is one the agent can use at will. Create a dedicated MCP account with only the
privileges it actually needs — read-only access to one schema is a completely
reasonable setting — rather than handing over `root`. The server enforces the
allow-list; the *privileges* are yours to choose.
</div>

### No database to point it at?

You do not need one. The MCP server can deploy a throwaway MariaDB instance
locally — no Docker, no container runtime, no administrator rights:

<div class="prompt" markdown="1">
*Deploy a MariaDB sandbox on port 3310.*

*Which MariaDB server versions can you deploy? Give me one on 12.3 and one on
11.8.*
</div>

Sandbox instances live under `~/.mariadb-shell/sandboxes/<port>/` on macOS and
Linux, and `%USERPROFILE%\MariaDB\mariadb-shell\sandboxes\<port>\` on Windows.
Five things to know:

- **You do not need MariaDB Server installed.** `sandbox.deploy` looks for a
  server in three places, in order: the `PATH`, then the versions it has already
  downloaded, then its published index — from which it fetches one, verifies its
  SHA-256 and unpacks it. A machine with a suitable server on `PATH` downloads
  nothing.
- **You can ask for a specific version**, and leave levels off it: `11.8.9`,
  `11.8` or just `11`, each satisfied by the newest release below it.
  `sandbox.list_available_versions` says what is on offer for your platform.
- A connection to the sandbox is **registered with the MCP server automatically**,
  so the agent can connect to it without you running `mcp setup` again.
- The sandbox is deployed **without TLS**, so command-line clients may need
  `--skip-ssl`.
- It creates a `root@'%'` account and listens on all interfaces — worth changing
  outside a trusted network.

## Step 3 — Run the working example
{: #step-3-run-the-working-example}

Everything is in place. The first tutorial is a complete round trip that uses
both halves of the plugin: the skills design a schema the MariaDB way, and the
MCP tools deploy a server and run it.

<div class="prompt" markdown="1">
*Create a MariaDB database schema for a note-taking app and store it in
`notes_app.sql`. Then spin up a sandbox instance on port 3310, connect to it and
run the script. Finally, list the tables you created.*
</div>

That is the whole tutorial in one paragraph — but the tutorial walks through
what the agent does at each step, what to check, and what to do when something
refuses.

<a class="btn btn--primary" href="{{ '/tutorials/notes-app-sandbox/' | relative_url }}">Start Tutorial 1 &rarr;</a>

## What to ask for

Some starting points, grouped by what they need.

**Skills alone**, no database connection:

<div class="prompt" markdown="1">
*Write a `CREATE TABLE` for a product catalogue, MariaDB style.*

*What changes if I move this application from MySQL to MariaDB?*

*How do I do semantic search in MariaDB?*

*Show me how to connect to MariaDB from Node.js.*
</div>

**With the MCP server connected**, against a real database:

<div class="prompt" markdown="1">
*What does the schema of my `orders` table look like?*

*Why is this query slow? Run `EXPLAIN` on it.*

*Which of my tables have no primary key?*

*Deploy a test instance and try this migration on it first.*
</div>

## Troubleshooting

**"Not a configured connection."** The URI the agent used is not on the
allow-list. Run `mariadb-shell -- mcp setup` and add it. Note that equivalent
spellings are folded together — a `mariadb://` prefix, host case, the default
port and an inline password all resolve onto the stored key. What is refused is
a URI asking for *more* than was configured, such as a default schema
(`…:3306/mydb`) or an option (`?ssl-mode=REQUIRED`), so that you are never
handed a connection that quietly drops what it asked for.

**A tool call hangs, or a path is rejected.** Every file-touching tool is gated
by the allowed-paths list. A path that is not on it falls back to an interactive
prompt the agent cannot answer. Add the directory with `mcp setup`.

**The agent cannot see the `migrator.*` tools.** They are only registered when
the migration tooling is installed. Run
`mariadb-shell -- mcp setup --installMigrator`, then restart the MCP server —
the change takes effect on the next server start, not the current one.

**On Windows, the MCP server dies with `No module named 'pywintypes'`.** The
Windows `mariadb-shell` packages do not yet bundle pywin32. Install it into the
shell's bundled Python as a workaround:
`pip install pywin32` against `<install>/lib/Python3.14/`.

**Nothing at all happened.** Check the plugin actually loaded. In Claude Code,
`/plugin` lists what is installed; in Codex, `/plugins`. In pi, remember that a
project-local package needs `--approve` at run time or it is configured and
never loaded.

**In pi, `/mcp` doesn't list the `mariadb` server.** You need Pi 1.0 or later,
and no `pi-mcp-adapter`: the adapter replaces Pi's built-in MCP, so the server
the plugin registers never connects. Run `pi remove npm:pi-mcp-adapter`, then
turn the built-in `mcp` back on in `pi config`.
