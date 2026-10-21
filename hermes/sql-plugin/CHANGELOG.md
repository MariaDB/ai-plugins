# Changelog

All notable changes to the MariaDB SQL Hermes Agent plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- The MariaDB SQL language server launcher, `scripts/mariadb-lsp-launcher.sh`
  (`.cmd` on Windows), for `mariadb-lsp` from mariadb-shell 26.10.3 and later.
  Hermes plugins cannot register a language server, so the README gives the
  `lsp.servers` entry to add to `~/.hermes/config.yaml`. The launcher never
  installs anything: it waits for the MCP launcher's install, so the package
  is downloaded once.

### Changed

- When the MCP launcher starts a first install of mariadb-shell, it now says
  on stderr that the install still finishes if the harness gives up on the
  server meanwhile (Claude Code waits 30 seconds unless `MCP_TIMEOUT` is
  raised), and how to reconnect afterwards.
- The `LICENSE` file is updated to include the licenses of the latest
  third-party components.

## [26.10.4] - 2026-10-19

### Added

- A guard that stops the agent from using the MariaDB and MySQL command-line
  clients for what the `mariadb` MCP server's tools do, so no password reaches a
  command line, the process list, logs or the model: `mariadb`/`mysql` running
  SQL, `mariadb-shell`/`mysqlsh` in SQL mode or calling an API a tool wraps (`--
  util dump-schemas`), and `mariadb-dump` piped into another client. Everything
  the tools do not cover still runs. It is the new, separate `mariadb-guard`
  package (`hermes/guard-plugin`, install it next to this one), because Hermes
  runs hooks only from a Python plugin. A blocked command is answered with the
  tool to use instead. `MARIADB_PLUGIN_ALLOW_CLI=1` turns it off.

### Changed

- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.10.2`, the newest published `mariadb-shell` release. An
  install already at or above that version is still used as-is; only a machine
  below it fetches anything.
- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `a439473` (synced 2026-10-19). The upstream default branch moved on, but
  nothing under `agent-skills/` did, so this plugin's 47 skills are unchanged.
- Version bumped to 26.10.4 to stay in lockstep with the other plugins.

## [26.10.3] - 2026-10-15

### Added

- First release of the plugin for Hermes Agent, as `mariadb-sql`: a portable
  Agent Plugins v1 package (`plugin.json`, `skills/`, `mcp.json`) installed with
  `hermes plugins install mariadb/ai-plugins#hermes/sql-plugin`.
- 47 skills, the same set the other harnesses' sql plugins ship: vendored
  from `mariadb-corporation/mariadb-docs` `agent-skills/` at commit `cc8dd40`, plus this
  repository's own `additional-skills/`.
- The `mariadb` MCP server, declared in `mcp.json`: the launcher finds or installs
  `mariadb-shell` (minimum `26.10.1`, set by `MARIADB_SHELL_VERSION`) and runs
  it as a stdio MCP server.
