# Changelog

All notable changes to the MariaDB Hermes Agent plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- First release of the plugin for Hermes Agent, as `mariadb-dev`: a portable
  Agent Plugins v1 package (`plugin.json`, `skills/`, `mcp.json`) installed with
  `hermes plugins install mariadb/ai-plugins#hermes/dev-plugin`.
- 85 skills, the same set the other harnesses' dev plugins ship: vendored
  from `mariadb-corporation/mariadb-docs` `agent-skills/` at commit `8bb700f`, plus this
  repository's own `additional-skills/`.
- The `mariadb` MCP server, declared in `mcp.json`: the launcher finds or installs
  `mariadb-shell` (minimum `26.10.1`, set by `MARIADB_SHELL_VERSION`) and runs
  it as a stdio MCP server.
