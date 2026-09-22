# Changelog

All notable changes to the MariaDB SQL Codex plugin are documented here.
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

### Fixed

- **The plugin now registers a working MCP server by itself, on every OS.**
  Installing it used to be a two-step affair: Codex expands no placeholder when
  it spawns a plugin's server (it execs the stored `command` verbatim), so the
  `${CLAUDE_PLUGIN_ROOT}` a plugin has to use died as a literal path, and
  `scripts/setup-codex-mcp.sh` had to register the server by absolute path.
  `.mcp.json` now uses a *relative* command plus `"cwd": "."` — which Codex does
  resolve, to the plugin's install directory — so no placeholder is needed.

  The command is deliberately **extensionless**, `./scripts/mariadb-mcp-launcher`,
  because `.mcp.json` cannot branch per OS and Windows cannot execute a `.sh`.
  Codex resolves the program per platform: unchanged on macOS/Linux, where the
  kernel runs the new shim of that name through its shebang; through `%PATHEXT%`
  on Windows, where it lands on `mariadb-mcp-launcher.cmd` instead and skips the
  extensionless file as not being a Windows binary.

  Verified against Codex 0.151.0 on both platforms, each installing the plugin
  into a clean `CODEX_HOME` with no `[mcp_servers]` entry of its own. On macOS and
  on Windows 11 (ARM64) alike the server came up and completed the MCP handshake,
  and on Windows a tool call reached it and returned a response. Codex's own
  resolver log states the choice outright there:

  ```text
  DEBUG codex_rmcp_client::program_resolver: Resolved "./scripts/mariadb-mcp-launcher"
    to "...\26.8.0\.\scripts\mariadb-mcp-launcher.cmd"
  ```

  A marker probe confirms the other half independently: with both launcher files
  present and each writing a distinct marker, only the `.cmd` wrote one — the
  extensionless file never executed.

  `scripts/setup-codex-mcp.{sh,cmd}` are kept as a documented fallback rather
  than a required step.

- **Codex 0.147 compatibility.** Three things kept this plugin from working as
  installed, all of them silent:
  - `.mcp.json` declared its server under `mcp_servers`; Codex reads only
    `mcpServers`, so it registered nothing at all. Renamed.
  - the command used `${CODEX_PLUGIN_ROOT}`, which is not a name Codex knows (it
    recognises `${CLAUDE_PLUGIN_ROOT}` alone). Renamed.
  - Codex resolves `dev@mariadb` through `.agents/plugins/marketplace.json`,
    falling back to `.claude-plugin/marketplace.json`, and never reads
    `.codex-plugin/marketplace.json` — so installing from this repo gave Codex the
    *Claude* plugin. The repo now ships `.agents/plugins/marketplace.json`, and the
    unread `.codex-plugin/marketplace.json` has been deleted rather than left to
    drift out of sync with it. (The per-plugin `.codex-plugin/plugin.json` stays —
    Codex does read that, and without it the installed version degrades to
    `local`.)
- **New `scripts/setup-codex-mcp.sh`.** Codex expands no placeholder when it
  spawns a plugin's MCP server, so a plugin cannot register a working one; the
  script does it with `codex mcp add` and an absolute path. Registering is now a
  documented second installation step.
- **New `scripts/setup-codex-mcp.cmd`** for native Windows. The bash script needs
  a shell Windows does not have, and the entry it writes names the `.sh` launcher
  — which Codex, spawning the command directly, cannot execute there. The batch
  version registers the `.cmd` launcher instead.

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

## [26.7.0] - 2026-07-20

### Added

- Initial release of the MariaDB SQL plugin for Codex.
- MariaDB agent skills vendored from
  [`mariadb-corporation/mariadb-docs/agent-skills`](https://github.com/mariadb-corporation/mariadb-docs/tree/main/agent-skills)
  (baseline MariaDB 11.8 LTS): SQL statement, function, and topical skills. The
  client-tool skills (`granular/tools`) are intentionally omitted from this
  SQL-focused plugin.
- Native `mariadb-shell` MCP server, launched via `scripts/mariadb-mcp-launcher.sh`
  (and `.cmd` for Windows), which detects OS/arch and downloads the matching
  release binary from `mariadb-corporation/mariadb-shell` into a user cache dir.
- Skills kept in sync by the repo-wide `scripts/sync-skills.sh`.
- Marketplace entry for `/plugin install`.
