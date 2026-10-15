# Changelog

All notable changes to the MariaDB contributor Hermes Agent plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [26.10.3] - 2026-10-15

### Added

- First release of the plugin for Hermes Agent, as `mariadb-contributor`: a portable
  Agent Plugins v1 package (`plugin.json`, `skills/`) installed with
  `hermes plugins install mariadb/ai-plugins#hermes/contributor-plugin`.
- 3 skills, the same set the other harnesses' contributor plugins ship:
  vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/` at commit `37cb1d3`.
