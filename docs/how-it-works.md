---
layout: page
title: How It Works
subtitle: >-
  Three moving parts — vendored skills, an MCP server, and the MariaDB Shell it
  runs inside. What each one is, why it is separate, and where the boundaries are.
permalink: /how-it-works/
description: The architecture of the MariaDB AI Plugins — vendored skills, the mariadb-shell MCP server, the launcher that installs the shell, and the security model.
---

## The three parts

Installing a plugin gives you three things that are genuinely separate. Knowing
which is which explains most of what happens when something does not work.

<div class="table-wrap" markdown="1">

| Part | What it is | Needs |
| --- | --- | --- |
| **Skills** | {{ site.skill_count }} Markdown documents vendored into the plugin. The agent reads the ones whose `description` matches what you asked. | Nothing. They work on a fresh install, offline. |
| **MCP server** | {{ site.tool_count }} tools that talk to a real MariaDB server, in three groups: `db.*`, `msm.*`, `sandbox.*`. | A one-time `mcp setup`, and a server to talk to. |
| **`mariadb-shell`** | MariaDB's command-line shell (a port of MySQL Shell). The MCP server runs **inside** it as a plugin. | Installed automatically on first use. |

</div>

## Why the MCP server lives inside the shell

It looks like an odd choice until you list what the shell already has:
high-performance database connections, a credential store backed by the
platform's secret keeping, sandbox deployment, and the schema-management engine.
Re-implementing any of those in a standalone MCP server would mean a second,
worse copy.

So the server is a shell plugin, and the practical consequences are:

- **Passwords never touch a config file.** They live in the shell's secret store.
  The agent asks for a *connection*, not for credentials.
- **`mariadb-shell` is also yours to use.** Run it and type `\help`. It is a
  perfectly good SQL client, and the sandboxes the agent creates are visible to
  it.
- **The shell's config home matters.** It is `~/.mariadb-shell`, and it holds the
  plugins, the secret store and the MCP server's own settings. A relocated or
  unreadable config home is behind a surprising share of "the tools are gone"
  reports.

## How the shell gets installed

Every plugin ships a launcher script — `mariadb-mcp-launcher.sh` and its `.cmd`
twin — and that script is what your harness actually spawns. It resolves a shell
in this order:

1. `$MARIADB_SHELL_BIN`, if set.
2. A `mariadb-shell` on `PATH` that meets the minimum version.
3. A local install at `$MARIADB_SHELL_BINDIR/mariadb-shell` (default
   `~/.local/bin`; on Windows `%LOCALAPPDATA%\Programs\mariadb-shell\bin\`).
4. Otherwise: fetch the official `install.sh` / `install.ps1` and run it, then
   launch what it installed.

<div class="callout" markdown="1">
**`MARIADB_SHELL_VERSION` (default `{{ site.shell_floor }}`) is a *minimum*, not a
target.** It decides whether a copy already on disk is acceptable. It is never a
trigger to go looking for something newer — a machine with an acceptable shell
does the whole resolution **with no network access at all**. A download happens
only when nothing on disk meets the floor.

Upgrade by raising the floor, by deleting the managed install, or by running
`install.sh` yourself.
</div>

The launcher writes every message it produces to **stderr**, because stdout *is*
the MCP JSON-RPC transport. A single stray byte on stdout breaks the protocol,
which is why the installer's output is redirected too.

## The security model

The MCP server refuses everything it has not been told about. There are two
allow-lists, both set by `mariadb-shell -- mcp setup`, and they are the whole
model.

### Connections

The agent cannot invent a host. `db.connect` checks its argument against the
configured connections, and `db.list_connections` is what an agent calls first
to find out what exists.

The matching normalizes equivalent spellings — a `mariadb://` or `mysql://`
scheme, host case, the default port, an inline password — so all of those open
the stored connection. What is refused is a URI asking for **more** than was
configured:

```text
root@127.0.0.1:3310/notes_app        → refused (a default schema)
root@127.0.0.1:3310?ssl-mode=REQUIRED → refused (an option)
```

That refusal is deliberate. Silently handing back a connection that dropped the
schema or the TLS requirement would be worse than saying no.

<div class="callout callout--tip" markdown="1">
**The privileges are the real boundary.** The allow-list controls *which server*
the agent reaches; the MariaDB account controls *what it can do there*. Give each
configured connection a dedicated account with only what it needs. Read-only on
one schema is a completely sensible setting, and far stronger than any prompt
instruction.
</div>

### Paths

Every file-touching tool — `db.execute_sql_script` with a `file_path`, all of
`msm.*`, `sandbox.deploy` with a `sandbox_dir` — is gated by an allowed-paths
list. A path that is not on it falls back to an interactive confirmation.

That fallback is why an unlisted path produces two different symptoms: for the
`msm.*` tools the call **fails**, and for `sandbox.deploy` it **hangs**, because
a headless agent cannot answer the prompt. Both mean the same thing — add the
directory with `mcp setup`.

### Connections a sandbox creates

`sandbox.deploy` registers `root@127.0.0.1:<port>` with its password, so the
agent can connect to the instance it just made without you re-running setup.
This is the one path by which a connection appears that you did not configure
by hand — and it points only at a throwaway server on localhost that the same
agent just created.

## The plugin variants

Each harness ships the same three variants, all built by the same
[`scripts/sync-skills.sh`]({{ site.repo }}/blob/main/scripts/sync-skills.sh):

<div class="table-wrap" markdown="1">

| Variant | Skills | MCP server |
| --- | --- | --- |
| `dev` | The full set — statements, functions, tools, connectors, topical, plus everything in `additional-skills/` | yes |
| `sql` | A SQL-focused subset — statements, functions, topical, plus `additional-skills/sql/` | yes |
| `contributor` | Skills for contributing to MariaDB tooling itself | no |

</div>

The folders are `<harness>/{dev,sql,contributor}-plugin/` for `claude/`,
`codex/` and `opencode/`. `pi/` ships `dev` only.

## How the harnesses differ

The content is identical; the packaging is not.

- **Claude Code** and **Codex** both read a marketplace manifest and install a
  plugin directory. Codex reads `.agents/plugins/marketplace.json`.
- **OpenCode** has no marketplace, so its plugin is wired up by hand: one `mcp`
  block merged into your config, an env var, and a symlink for the skills.
- **Pi** has no marketplace. A pi package is any directory with a `pi` field in
  its `package.json`, so the **repo-root `package.json` is the manifest** and the
  whole repository installs as one package. Its extension registers the MCP
  server with Pi's built-in MCP support (Pi 1.0+), which exposes the tools
  through codemode by default.

## Why the skills are vendored

The skills are copied into each plugin rather than fetched at run time. That is a
deliberate trade: it means a plugin release pins a skill version, so what you
tested is what you ship, and an upstream edit never changes an agent's behaviour
mid-session.

The cost is that editing `additional-skills/` without re-running
`scripts/sync-skills.sh` silently ships stale text. There is a test for exactly
that now — every vendored `additional`-layer skill must be byte-identical to its
source — because it went unnoticed for four days once.

## Where to go from here

- [Get Started]({{ '/get-started/' | relative_url }}) — install and configure.
- [MCP Tool Reference]({{ '/mcp-tools/' | relative_url }}) — every tool and its arguments.
- [Skill Catalog]({{ '/skills/' | relative_url }}) — what the agent can read.
- [CONTRIBUTING.md]({{ site.repo }}/blob/main/CONTRIBUTING.md) — working on the
  plugins rather than with them.
