# Changelog

All notable changes to the MariaDB contributor Hermes Agent plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [26.10.4] - 2026-10-19

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/`
  at commit `a4352a5` (synced 2026-10-19). `review-shell-change` adds two rules that
  change verdicts: a scenario the product cannot produce (state only a person
  can create by hand, such as rows written straight into the REST metadata
  schema) is not a finding, and a defect outside the change goes to a separate
  follow-up list rather than into the findings. The plugin keeps its 3 skills.
- Version bumped to 26.10.4 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor does not apply here.

## [26.10.3] - 2026-10-15

### Added

- First release of the plugin for Hermes Agent, as `mariadb-contributor`: a portable
  Agent Plugins v1 package (`plugin.json`, `skills/`) installed with
  `hermes plugins install mariadb/ai-plugins#hermes/contributor-plugin`.
- 3 skills, the same set the other harnesses' contributor plugins ship:
  vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/` at commit `37cb1d3`.
