# Changelog

All notable changes to the MariaDB contributor OpenCode plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [26.10.0] - 2026-10-02

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/`
  at commit `938d473` (synced 2026-10-02). Nothing under `.claude/skills/`
  changed, so the plugin's 3 skills are unchanged.
- Version bumped to 26.10.0 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor does not apply here.

## [26.9.5] - 2026-09-30

### Added

- `split-scripted-test` skill: splitting a long scripted test
  (`unittest/scripts/auto/*/scripts/*_norecord.py`) into parallel chunk groups
  for `run_unit_tests.py`, or rebalancing the groups of a test that is already
  split so every group takes about the same time. Vendored from
  `mariadb-corporation/mariadb-shell` `.claude/skills/` at commit `938d473`
  (synced 2026-09-30); brings the plugin to 3 skills.

### Changed

- Version bumped to 26.9.5 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor the others moved to 26.9.5 does not apply here.

## [26.9.4] - 2026-09-24

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/`
  at commit `8adaada` (synced 2026-09-24). The upstream default branch moved on,
  but nothing under `.claude/skills/` did, so both skills here are unchanged.
- Version bumped to 26.9.4 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor the others moved to 26.9.4 does not apply here.

## [26.9.3] - 2026-09-22

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/`
  at commit `291bf84` (synced 2026-09-22). The upstream default branch moved on,
  but nothing under `.claude/skills/` did, so both skills here are unchanged.
- Version bumped to 26.9.3 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor the others moved to 26.9.3 does not apply here.

## [26.9.2] - 2026-09-12

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/`
  at commit `1d859c7` (synced 2026-09-12). Nothing under `.claude/skills/`
  changed, so both skills here are unchanged.
- Version bumped to 26.9.2 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor the others moved to 26.9.2 does not apply here.

## [26.9.1] - 2026-09-08

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/`
  at commit `33b4e3e` (synced 2026-09-04). The upstream default branch moved
  on, but nothing under `.claude/skills/` did, so both skills here are
  unchanged.
- Version bumped to 26.9.1 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor the others moved to 26.9.1 does not apply here.

## [26.9.0] - 2026-09-02

### Added

- `review-shell-change` skill, bringing the plugin to two skills.

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-shell` `.claude/skills/`
  at commit `2b2d0aa` (synced 2026-09-01); the same sync refreshed
  `create-shell-plugin`.
- The bundled `LICENSE` is now the MariaDB Shell Licensing Information User
  Manual, re-copied from the repo root, in place of the bare GPL-2.0 text.
- Version bumped to 26.9.0 to stay in lockstep with the other plugins. This
  plugin ships skills only and no MCP server, so the `MARIADB_SHELL_VERSION`
  floor the others moved to 26.9.0 does not apply here.

## [26.7.0] - 2026-07-22

### Added

- Initial release of the MariaDB contributor plugin for OpenCode.
- Skills for contributing to MariaDB tooling, vendored from the
  `mariadb-corporation/mariadb-shell` repository's `.claude/skills/` tree by the
  repo-wide `scripts/sync-skills.sh`. Skills only — no MCP server yet.
