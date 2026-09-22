# Changelog

All notable changes to the MariaDB plugin for Pi are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/), and this
project adheres to [Semantic Versioning](https://semver.org/).

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

## [26.7.0] - 2026-07-30

### Added

- Initial release of the MariaDB plugin for the [Pi coding agent](https://pi.dev),
  packaged as a **pi extension** (`package.json` `pi` field declaring
  `extensions` + `skills`).
- The extension (`src/index.ts`) registers a `/mariadb-mcp-setup` command and, at
  session start, reminds the user to enable the MCP server when it isn't wired up.
- `pi-mcp-adapter` is declared as a dependency: the native `mariadb-shell` MCP
  server is surfaced to pi through the adapter's `mcp` proxy tool.
- `scripts/setup-pi-mcp.sh` registers the mariadb-shell server in the
  pi-mcp-adapter `mcp.json` config (global `~/.config/mcp/mcp.json` by default, or
  project-local `./.mcp.json` with `--project`); idempotent and merge-preserving.
- Native `mariadb-shell` launcher (`scripts/mariadb-mcp-launcher.sh` + `.cmd`),
  shared verbatim with the other plugins.
- MariaDB agent skills vendored flat from
  [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills)
  (baseline MariaDB 11.8 LTS) by the repo-root `scripts/sync-skills.sh`.
