# Changelog

All notable changes to the MariaDB guard plugin for Hermes Agent are documented
here. The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- First release, as `mariadb-guard`: a Python plugin installed next to
  `mariadb-dev` or `mariadb-sql`. Its `pre_tool_call` hook blocks a `terminal`
  call that uses a MariaDB or MySQL command-line client for what the `mariadb`
  MCP server's tools do (`mariadb`/`mysql` running SQL,
  `mariadb-shell`/`mysqlsh` in SQL mode or calling an API a tool wraps,
  `mariadb-dump` piped into another client) and names the tool to use instead;
  everything else still runs. A system-prompt section says the same up front.
  `MARIADB_PLUGIN_ALLOW_CLI=1` turns it off.
