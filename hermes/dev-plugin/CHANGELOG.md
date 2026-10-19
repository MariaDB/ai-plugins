# Changelog

All notable changes to the MariaDB Hermes Agent plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

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
  nothing under `agent-skills/` did, so this plugin's 85 skills are unchanged.
- Version bumped to 26.10.4 to stay in lockstep with the other plugins.

## [26.10.3] - 2026-10-15

### Added

- First release of the plugin for Hermes Agent, as `mariadb-dev`: a portable
  Agent Plugins v1 package (`plugin.json`, `skills/`, `mcp.json`) installed with
  `hermes plugins install mariadb/ai-plugins#hermes/dev-plugin`.
- 85 skills, the same set the other harnesses' dev plugins ship: vendored
  from `mariadb-corporation/mariadb-docs` `agent-skills/` at commit `cc8dd40`, plus this
  repository's own `additional-skills/`.
- The `mariadb` MCP server, declared in `mcp.json`: the launcher finds or installs
  `mariadb-shell` (minimum `26.10.1`, set by `MARIADB_SHELL_VERSION`) and runs
  it as a stdio MCP server.
