# Changelog

All notable changes to the MariaDB SQL Hermes Agent plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- When no suitable `mariadb-shell` is installed, the MCP launcher installs the
  release this plugin was tested with, `v` followed by `MARIADB_SHELL_VERSION`
  (now `v26.10.4`), instead of the newest release. A newer `mariadb-shell` you
  installed yourself is still used. The other harnesses' plugins keep installing
  the newest release.
- The launcher fetches the installer from a fixed `mariadb-shell` commit instead
  of `main`, and verifies the package against
  `scripts/mariadb-shell-v26.10.4.SHA256SUMS`, a copy of that release's checksums
  kept in this repository, instead of the file published with the release.
  `MARIADB_SHELL_TAG` installs another release, checked against its own
  `SHA256SUMS`.

### Removed

- The launcher's prerelease fallback and `MARIADB_SHELL_PRERELEASE`: a named
  release is installed whether or not it is a prerelease.
- The launcher no longer reads `MARIADB_SHELL_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`
  or `gh auth token`, and sends no credentials. `mariadb-shell` is public.

## [26.10.6] - 2026-10-24

### Changed

- The `LICENSE` file names the bundled-packages section's extension by its
  current name, MariaDB Shell for VS Code.
- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.10.4`, the newest published `mariadb-shell` release. An
  install already at or above that version is still used as-is; only a machine
  below it fetches anything.
- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `62ef6fe` (synced 2026-10-24). The upstream default branch moved on, but
  nothing under `agent-skills/` did, so this plugin's 47 skills are unchanged.
- Version bumped to 26.10.6 to stay in lockstep with the other plugins.

## [26.10.5] - 2026-10-21

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
- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.10.3`, the newest published `mariadb-shell` release and
  the first with `mariadb-lsp`. An install already at or above that version is
  still used as-is; only a machine below it fetches anything.
- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `12d4cd3` (synced 2026-10-21). The upstream default branch moved on, but
  nothing under `agent-skills/` did, so this plugin's 47 skills are unchanged.
- Version bumped to 26.10.5 to stay in lockstep with the other plugins.

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
