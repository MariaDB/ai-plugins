# Changelog

All notable changes to the MariaDB guard plugin for Hermes Agent are documented
here. The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [26.10.6] - 2026-10-24

### Changed

- The `LICENSE` file names the bundled-packages section's extension by its
  current name, MariaDB Shell for VS Code.
- Version bumped to 26.10.6 to stay in lockstep with the other plugins. This
  plugin has neither skills nor an MCP server, so the skills re-vendor and the
  `MARIADB_SHELL_VERSION` floor do not apply here.

## [26.10.5] - 2026-10-21

### Changed

- The `LICENSE` file is updated to include the licenses of the latest
  third-party components.
- Version bumped to 26.10.5 to stay in lockstep with the other plugins. This
  plugin has neither skills nor an MCP server, so the skills re-vendor and the
  `MARIADB_SHELL_VERSION` floor do not apply here.

## [26.10.4] - 2026-10-19

### Added

- First release, as `mariadb-guard`: a Python plugin installed next to
  `mariadb-dev` or `mariadb-sql`. Its `pre_tool_call` hook blocks a `terminal`
  call that uses a MariaDB or MySQL command-line client for what the `mariadb`
  MCP server's tools do (`mariadb`/`mysql` running SQL,
  `mariadb-shell`/`mysqlsh` in SQL mode or calling an API a tool wraps,
  `mariadb-dump` piped into another client) and names the tool to use instead;
  everything else still runs. A system-prompt section says the same up front.
  `MARIADB_PLUGIN_ALLOW_CLI=1` turns it off.
