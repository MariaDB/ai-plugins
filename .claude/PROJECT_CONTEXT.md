# Project Context

Index. Each area below lives in its own file under `.claude/context/` — read the
ones your work touches, not the whole set. This file keeps the description, the
layout, the context-file table and the current git state.

## Project

**Latest work streams**: (**NEW**) **Release 26.9.4 is IN PROGRESS** on `wip/26.9.4`, the first cut with the new **`/release <version>` command** (PR #25, `5d07abf`): both versions to 26.9.4 (33 + 17 files), a provenance-only re-vendor, CHANGELOG entries, static tier green; tag, prereleases and the fork sync follow the merge. See [release history](context/release-history.md). (0) **Release 26.9.3 is SHIPPED** (PR #20, squash `b6ed467`; annotated tag `v26.9.3` = object `a38774d`, published as a prerelease on both repos): both versions to 26.9.3, a skills re-vendor that changed nothing but provenance, and CHANGELOG entries for 26.9.3 *and* — retroactively — 26.9.2, which had shipped with none. **Tags and releases now run v26.9.0 → v26.9.3 with no gaps on both repos**, and `origin` carries only `main` now that the stale `wip/*` remotes are deleted. See [release history](context/release-history.md). (0) **DevHub polish — merged as PR #18** (squash `054e1a5`, 2026-09-15; `wip/docs-improvements` now deleted): an `MCP` nav link, `.btn--primary` re-skinned from mariadb.com's own button classes, and two hero-card fixes for narrow panels. See "DevHub polish" in [current state](context/current-state.md). (0) **The DevHub is merged and LIVE** at **https://ai-plugins.mariadb.com/** — PR #12 landed as `ed6fd43`, then #14, #15, and a custom domain (`docs/CNAME` + `baseurl: ""`). A static Getting Started site in `docs/`, served by GitHub Pages' built-in Jekyll from `main` + `/docs`. Ten tutorials, a filterable catalog, four learning paths, a generated skill catalog, an architecture page and an MCP tool reference. It also grew tooling that reaches outside `docs/`: `scripts/sync-skills.sh` now regenerates the site's skill data as its last step. See "DevHub (`docs/`)" in [architecture](context/architecture.md). (0) **Release 26.9.1 is out** (2026-09-08, tag `v26.9.1` = `4003d0d`, prerelease on both repos). It merged two independently-moved versions — the **mariadb-shell floor** (direct to `main`, `a693a28`) and the **plugin package version** (PR #11) — and shipped the repo-local **`mariadb-migrator`** skill (MySQL→MariaDB via the `migrator.*` MCP tools; new `additional-skills/migrator/` subfolder, dev plugins 75 → 76 skills), a skills re-vendor, a new **`CONTRIBUTING.md`** holding the maintainer docs, and README fixes. (a) **Codex now registers its own MCP server** — merged as PR #6; see Codex fact 5 in [architecture](context/architecture.md). (b) **`db.connect` coverage** on `wip/DB-CONNECT-TESTS`, which closed the last untested path an agent actually takes. (c) **PR transfers from the tracking fork** `MariaDB/ai-plugins` (remote `fork`) into `origin` — both of its PRs are transferred and merged (#9, #7). Earlier stream, merged:  rewrote the `mariadb-mcp-launcher.{sh,cmd}` scripts in all plugins to stop downloading release assets themselves and instead delegate to the shell's own `install.sh` / `install.ps1`; bumped the version gate to 26.8.0 (now explicitly a *minimum*); added a repo-root `LICENSE`, `.gitattributes` and `SECURITY.md`; restructured the main README (Installation moved directly under the harness table, new `## Plugin variants` heading, new "configure the MCP server" step propagated to all 7 MCP-bearing plugin READMEs); switched the install-facing org to **`mariadb`**; and added the GPL-2.0 copyright header to all 46 source files. Details in "Launcher rewrite" below.

`ai-plugins` packages MariaDB agent skills (+ the native `mariadb-shell` MCP server) as installable plugins for four coding agents: Claude Code (`claude/`), Codex (`codex/`), OpenCode (`opencode/`), and Pi/pi.dev (`pi/`). Each agent has `dev` (full skills + MCP), `sql` (SQL subset + MCP), `contributor` (skills-only) variants. Skills are vendored (never hand-edited) by `scripts/sync-skills.sh`. **This work stream** added a set of **MariaDB REST Service** skills (a fork of the MySQL REST Service) and **Schema Management (MSM)** lifecycle skills under `additional-skills/`, reorganized `additional-skills/` into `sql/`/`rest/`/`schema-management/` subfolders with per-plugin selection, added **two Claude e2e tests** that exercise the REST skills and the MSM lifecycle skills end-to-end (both pass), and updated the README. Latterly it also **unified how the tests run** across the plugins: a repo-root `run_tests.py` drives every suite with the Python inside `mariadb-shell` and one combined coverage report, and the `db` tier deploys its own sandbox instance instead of needing a server on 3306.

## Repo layout

| Path | What it is |
| --- | --- |
| `claude/`, `codex/`, `opencode/`, `pi/` | One dir per coding agent, each with `dev` / `sql` / `contributor` plugin variants plus its `*-plugin-test*` suite |
| `additional-skills/` | This repo's own skills, in `sql/` `rest/` `schema-management/` `migrator/`, plus the sources & licensing README |
| `docs/` | The DevHub — Jekyll site served by GitHub Pages, live at https://ai-plugins.mariadb.com/ |
| `scripts/` | `sync-skills.sh` (vendors skills), `set-plugin-version.sh`, `set-mariadb-shell-version.sh` |
| `run_tests.py`, `pytest-coverage.ini` | Unified runner across every suite, one combined coverage report |
| `package.json` | The pi manifest (`pi` field + `pi-mcp-adapter`) |
| `test-results/`, `htmlcov/` | Test and coverage output, gitignored |
| `README.md`, `CONTRIBUTING.md`, `LICENSE`, `SECURITY.md` | Root docs; `CONTRIBUTING.md` holds the maintainer docs |

## Context files

| File | What's in it |
| --- | --- |
| [`context/architecture.md`](context/architecture.md) | Non-obvious design choices and why — plugin/variant model, skill vendoring, MCP wiring, test tiers |
| [`context/current-state.md`](context/current-state.md) | What works, what's in progress, what's broken — includes the DevHub polish stream |
| [`context/files-that-matter.md`](context/files-that-matter.md) | Path → purpose for the files central to this work, with their editing traps |
| [`context/next-steps.md`](context/next-steps.md) | Concrete ordered list of what to do next |
| [`context/gotchas.md`](context/gotchas.md) | Dead ends already tried and why they failed — read before retrying anything |
| [`context/repo-conventions.md`](context/repo-conventions.md) | The two remotes and the fork's role, and the merged-branch deletion rule |
| [`context/release-history.md`](context/release-history.md) | What landed on `main`, newest first, and the per-release notes |

## Git state

`git status --short` at checkpoint time: clean apart from this checkpoint's own
edits, committed on the release branch so they ship in the release PR.

`git branch --show-current`: **`wip/26.9.4`**, four release commits ahead of
`main` (shell floor, plugin version, re-vendor, CHANGELOG) plus this
checkpoint. `main` is level with `origin/main` at `5d07abf` (#25, the
`/release` command). `origin` otherwise carries only `main`.

**The release PR is about to open** from `wip/26.9.4`. Recently merged: **#25**
`5d07abf` (`/release` command), **#24** `2a63cc2` and **#23** `359e610` (the
`.org` fork domain), **#20** `b6ed467` (release 26.9.3).

**Tags and releases run v26.9.0 → v26.9.3 with no gaps**, each an annotated tag
pushed to `origin` **and** `fork` as the same object, each a **prerelease** on
both repos. `v26.9.4` does not exist yet. `releases/latest` 404s on both — the
endpoint excludes prereleases, and nothing consumes it.

Both remotes are present (`git remote -v`): `origin` =
`mariadb-corporation/ai-plugins`, `fork` = `mariadb/ai-plugins`. `fork/main` is
`origin/main` as of #24 plus the fork-only `docs/CNAME` / `_config.yml` `url:`.
See [repo conventions](context/repo-conventions.md) for what each is for.
