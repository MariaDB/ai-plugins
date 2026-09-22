# Changelog

All notable changes to the MariaDB SQL OpenCode plugin are documented here.
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
  but nothing under `agent-skills/` did, so this plugin's 47 skills are
  unchanged.
- Version bumped to 26.9.3 to stay in lockstep with the other plugins.

## [26.9.2] - 2026-09-12

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `0e7e033` (synced 2026-09-12). **No skill in this plugin changed**: the
  `mariadb-migrator` split that took the dev plugins from 76 to 82 skills is
  dev-only, so this plugin's 47 skills are unchanged.
- `MARIADB_SHELL_VERSION` now defaults to `26.9.2`.
- Version bumped to 26.9.2 to stay in lockstep with the other plugins.

## [26.9.1] - 2026-09-08

### Changed

- Skills re-vendored from `mariadb-corporation/mariadb-docs` `agent-skills/` at
  commit `71f3ac5` (synced 2026-09-04). **No skill in this plugin changed**: the
  upstream edits were to the connector layer and the new `mariadb-migrator`
  skill is repo-local, and both are dev-only. This plugin's 47 skills are
  unchanged.
- `MARIADB_SHELL_VERSION`, the *minimum* `mariadb-shell` the launcher accepts,
  now defaults to `26.9.1`, matching the published release series. An install
  already at or above that version is still used as-is; only a machine below it
  fetches anything.
- Version bumped to 26.9.1 to stay in lockstep with the other plugins.

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

## [26.7.0] - 2026-07-20

### Added

- Initial release of the MariaDB SQL plugin for OpenCode.
- MariaDB agent skills vendored from
  [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills)
  (baseline MariaDB 11.8 LTS): SQL statement, function, and topical skills. The
  client-tool skills (`granular/tools`) are intentionally omitted from this
  SQL-focused plugin.
  - Vendored in a flat layout, since OpenCode discovers skills only one directory deep.
- Native `mariadb-shell` MCP server, configured in `opencode.json` and launched via
  `scripts/mariadb-mcp-launcher.sh` (and `.cmd` for Windows), which detects OS/arch
  and downloads the matching release binary from `mariadb-corporation/mariadb-shell`
  into a user cache dir.
- Skills kept in sync by the repo-wide `scripts/sync-skills.sh` (flat layout for this
  target).
