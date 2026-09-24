# Changelog

All notable changes to the MariaDB OpenCode plugin are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

## [26.9.4] - 2026-09-24

### Changed

- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.9.4`, matching the published release series. An install
  already at or above that version is still used as-is; only a machine below it
  fetches anything.
- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `bb6522c` (synced 2026-09-24). The upstream default branch moved on,
  but nothing under `agent-skills/` did, so all 82 skills here are unchanged.
- Version bumped to 26.9.4 to stay in lockstep with the other plugins.

## [26.9.3] - 2026-09-22

### Changed

- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.9.3`, matching the published release series. An install
  already at or above that version is still used as-is; only a machine below it
  fetches anything.
- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `1a89bd3` (synced 2026-09-22). The upstream default branch moved on,
  but nothing under `agent-skills/` did, so all 82 skills here are unchanged.
- Version bumped to 26.9.3 to stay in lockstep with the other plugins.

## [26.9.2] - 2026-09-12

### Changed

- The `mariadb-migrator` skill is now an overview plus six topic skills
  (`-configure`, `-discovery`, `-modes`, `-run`, `-verify` and
  `-troubleshooting`), so a migration loads only the topic it needs rather than
  one large skill. Takes the plugin from 76 to 82 skills.
- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `0e7e033` (synced 2026-09-12).
- `MARIADB_SHELL_VERSION` now defaults to `26.9.2`.
- Version bumped to 26.9.2 to stay in lockstep with the other plugins.

## [26.9.1] - 2026-09-08

### Added

- `mariadb-migrator` skill: migrating a MySQL database to MariaDB with the
  `migrator.*` tools of the `mariadb-shell` MCP server — picking the execution
  mode, writing the tooling's `config/migration.yaml` correctly (only servers
  that are already configured MCP connections may be named, and passwords are
  never written to it), then planning, running and verifying the migration. It
  also records the release's known defects and the configuration that works
  around each, so a run does not have to rediscover them. Brings the plugin to
  76 skills.

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `71f3ac5` (synced 2026-09-04): `mariadb-connector-r2dbc-install` and
  `mariadb-connector-r2dbc-usage` now document R2DBC driver 1.4.2 in place of
  1.4.1. No upstream skill was added or removed, so the skill count moved only
  by the one added above.
- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.9.1`, matching the published release series. An install
  already at or above that version is still used as-is; only a machine below it
  fetches anything.

## [26.9.0] - 2026-09-02

### Changed

- The MCP launcher scripts are **enabled**: they were shipped as
  `mariadb-mcp-launcher.sh_disabled` / `.cmd_disabled`, so the `command` in
  `opencode.json` pointed at a file that did not exist.
- The launcher now **prefers a stable release and falls back to a prerelease**
  when there is no stable one to install, so no `MARIADB_SHELL_PRERELEASE=1` is
  needed while `mariadb-shell` has only prereleases. Setting it to `1` still skips
  straight to a prerelease, and `0` refuses one and keeps the install
  stable-only.
- The `mariadb-shell` launcher no longer downloads and unpacks release assets
  itself. It now runs the first shell that satisfies `MARIADB_SHELL_VERSION`
  (`$MARIADB_SHELL_BIN`, one on `PATH`, or an existing install in `~/.local/bin`
  / `%LOCALAPPDATA%\Programs\mariadb-shell\bin`), and otherwise delegates to the
  shell's own `install.sh` / `install.ps1` — which selects the package for this
  OS, CPU and glibc version and verifies it against the release's `SHA256SUMS`.
  Asset naming is no longer duplicated here, so the launcher cannot go stale as
  releases change.
- `MARIADB_SHELL_VERSION` now means the *minimum* acceptable version and defaults
  to `26.9.0`, matching the published release series.
- New pass-through settings: `MARIADB_SHELL_BINDIR`, `MARIADB_SHELL_PREFIX`,
  `MARIADB_SHELL_TAG`, `MARIADB_SHELL_PRERELEASE` (needed while the only
  published release is a prerelease) and `MARIADB_SHELL_TOKEN` (`GH_TOKEN`,
  `GITHUB_TOKEN` and `gh auth token` are still honoured).

## [26.7.0] - 2026-07-05

### Added

- Vendored the repo-local `additional-skills/` tree alongside the upstream skills:
  `mariadb-schema-create-script` (25 skills total). These are recorded in the
  manifest under an `additional` layer.

### Changed

- The flat skill layout (already used by OpenCode) is now shared by every plugin
  in the repo, so all three are identical on disk.

## [0.0.1] - 2026-06-30

### Added

- Initial release of the MariaDB plugin for OpenCode.
- 24 MariaDB agent skills vendored from
  [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills)
  (baseline MariaDB 11.8 LTS):
  - 12 granular statement skills, 5 function skills, 2 tool skills, 5 topical skills.
  - Vendored in a flat layout, since OpenCode discovers skills only one directory deep.
- Native `mariadb-shell` MCP server, configured in `opencode.json` and launched via
  `scripts/mariadb-mcp-launcher.sh` (and `.cmd` for Windows), which detects OS/arch
  and downloads the matching release binary from `mariadb-corporation/mariadb-shell`
  into a user cache dir.
- Skills kept in sync by the repo-wide `scripts/sync-skills.sh` (flat layout for this
  target).
