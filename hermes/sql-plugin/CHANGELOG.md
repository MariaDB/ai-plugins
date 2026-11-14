# Changelog

All notable changes to the MariaDB SQL Hermes Agent plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [26.11.0] - 2026-11-14

### Added

- The MCP server is given `MARIADB_RESTD_VERSION` (26.11.0): the lowest MariaDB
  REST Daemon it accepts when an agent sets one up without naming a version. It
  moves with the newest rest-daemon release, as `MARIADB_SHELL_VERSION` does
  with the shell's (`scripts/set-mariadb-restd-version.sh`).
- mariadb-restd is pinned as the shell is: the launchers pass on
  `MARIADB_RESTD_TAG` (`v` and the restd floor) and the committed
  `scripts/mariadb-restd-v<version>.SHA256SUMS`, so the MCP server installs
  exactly that release, verified against those checksums.

### Changed

- The `LICENSE` file follows legal's review: MariaDB plc, for its
  modifications and additions, also grants the additional permission to
  link with separately licensed software, and the third-party list adds
  the packages the VS Code extension's notebooks bundle (sucrase and its
  dependencies, acorn).
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
- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.11.2`, the newest published `mariadb-shell` release. An
  install already at or above that version is still used as-is; only a machine
  below it fetches anything.
- The launchers' committed checksum file moves with the floor, to
  `scripts/mariadb-shell-v26.11.2.SHA256SUMS`.
- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `114a4b7` (synced 2026-11-14). `mariadb-string-functions` adds the two
  XML functions, `EXTRACTVALUE` and `UPDATEXML`, which query and update XML
  strings with XPath; this plugin's 47 skills are otherwise unchanged.
- Version bumped to 26.11.0 to stay in lockstep with the other plugins.

### Removed

- The launcher's prerelease fallback and `MARIADB_SHELL_PRERELEASE`: a named
  release is installed whether or not it is a prerelease.
- The launcher no longer reads `MARIADB_SHELL_TOKEN`, `GH_TOKEN`, `GITHUB_TOKEN`
  or `gh auth token`, and sends no credentials. `mariadb-shell` is public.

### Fixed

- On macOS and Linux, launchers started at the same time no longer all fail
  to install `mariadb-shell`. Before, two sessions starting together, or a session and
  another tool installing `mariadb-shell`, each ran the installer into the same
  folder, and every one of them failed. Now they take turns through a lock folder
  in the install prefix, and the ones that waited start the shell the first one
  installed. After a failed install, the launcher starts a shell that meets
  `MARIADB_SHELL_VERSION` if one appeared meanwhile, and starts an older one,
  with a warning, only when there is none. `MARIADB_SHELL_LOCK_WAIT` (default
  180 s) limits the wait.
- On Windows, launchers started at the same time no longer fail over the
  installer script: each downloads it into a temporary folder of its own, where
  before they could share one file name and all but one failed. After
  installing, the launcher starts any shell that meets
  `MARIADB_SHELL_VERSION`, whoever installed it, and an older one, with a
  warning, only when there is none.
- On Windows, a first install started from PowerShell 7 (a `pwsh` terminal, for
  instance) no longer fails with "The term 'Get-FileHash' is not recognized":
  the launcher clears `PSModulePath`, so the Windows PowerShell it runs loads its
  own modules rather than PowerShell 7's.
- The launchers read all of `mariadb-shell --version` for the version, not
  only its first line, which a build can fill with other messages.

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
