# Project Context

Index. Each area below lives in its own file under `.claude/context/` — read the
ones your work touches, not the whole set. This file keeps the description, the
layout, the context-file table and the current git state.

## Project

**Latest work streams**: (**NEW**) **MSM skill fixes — MERGED as PR #41** (`2a6ab29`, 2026-10-06; unreleased): section rules corrected in the schema-management skills, e2e tests, docs-ref and DevHub; the PR also added `/read-checkpoint` and dropped `/checkpoint`'s subfolder argument. See [release history](context/release-history.md). (0) **Release 26.10.0 — SHIPPED** (PR #39, squash `68bd7d4`; tag `v26.10.0` = object `ed68f6a`, prerelease on both repos; fork fast-forwarded): the first release whose plugin version is decoupled from the mariadb-shell floor (floor stays 26.9.5); ships #37 (Pi 1.0 MCP) and a provenance-only re-vendor. See [release history](context/release-history.md). (0) **Plugin version decoupled from the shell version** (2026-10-02): `/release <version> [shell-version]` no longer requires the plugin version to equal a mariadb-shell release; the floor moves only when asked. Next release **26.10.0** ships on top of floor 26.9.5. See [release history](context/release-history.md). (0) **Pi 1.0 built-in MCP — MERGED as PR #37** (`5711b11`, 2026-10-02): the pi extension now registers the `mariadb` server with Pi 1.0's own MCP (`pi.registerMcpServer`), so `pi install` is the whole setup; `pi-mcp-adapter` (which would replace the built-in MCP), `/mariadb-mcp-setup` and `setup-pi-mcp.sh` are gone; every Pi doc page carries the migration steps; the pi e2e runs in a throwaway `PI_CODING_AGENT_DIR` and makes a real codemode MCP call (static 691, e2e 5 passed). Not yet released. See [architecture](context/architecture.md) and [gotchas](context/gotchas.md). (0) **Code fences in the reference docs — MERGED as PR #36** (`0d77b1e`, 2026-10-02): per reviewer feedback, everything the reader types is in a fenced block with a language (`bash`/`batch`/`sql`/`text`), Basic Usage's prompts included; the `mcp.setup()` note now says SQL-mode start, `\py` first (MariaDB Shell has no JS mode). Rule recorded in [reference docs](context/docs-ref.md). (0) **Reference docs in `docs-ref/` — MERGED as PR #35** (`17bce4b`, 2026-10-01): GitBook source for the Enterprise Tools space of mariadb.com/docs (41 pages) plus an offline Docusaurus preview in the live site's theme. See [reference docs](context/docs-ref.md). Alongside it, **PR #34** (`4e2e6d5`) corrected the DevHub: `db.execute_sql_script` runs a whole script on ONE session (verified through the MCP server), and updated the favicons. (0) **DevHub re-skinned on mariadb.org** — #32 `81f72fa` (palette + space banner) and #33 `c084a21` (mariadb.org's header and footer rebuilt; sponsor logos hot-linked; the `-dark.svg` logos since replaced by a dark-mode drop-shadow on the regular ones). See the DevHub entry in [current state](context/current-state.md). (0) **Release 26.9.5 is SHIPPED** (PR #30, squash `dec6f52`; tag `v26.9.5` = object `c2aa50f`, prerelease on both repos): both versions to 26.9.5, a re-vendor that shipped content (`mariadb-explain` fix; new contributor skill `split-scripted-test`), counts 85 / 47 / 3, and the Laravel skills' first release. **The fork's `main` was force-pushed to `dec6f52`** (user's call) after the sync merge conflicted, so both repos now share one `main` commit. See [release history](context/release-history.md). (0) **Laravel skills — MERGED as PR #28** (`9eb9119`), transferred from fork PR 4 (@Rhaima96, now closed): a new dev-only `additional-skills/laravel/` subfolder with three skills (dev 82 → 85). The transfer recipe is in [repo conventions](context/repo-conventions.md). (0) **DevHub served only from `ai-plugins.mariadb.org`** — PR #29 (`2e83366`). (0) **Release 26.9.4 is SHIPPED** (PR #26, squash `2bbdb2a`; tag `v26.9.4` = object `f0e1c3c`, prerelease on both repos; fork synced as `22bd0be`), the first cut with the new **`/release <version>` command** (PR #25, `5d07abf`): both versions to 26.9.4 (33 + 17 files), a provenance-only re-vendor, CHANGELOG entries. See [release history](context/release-history.md). (0) **Release 26.9.3 is SHIPPED** (PR #20, squash `b6ed467`; annotated tag `v26.9.3` = object `a38774d`, published as a prerelease on both repos): both versions to 26.9.3, a skills re-vendor that changed nothing but provenance, and CHANGELOG entries for 26.9.3 *and* — retroactively — 26.9.2, which had shipped with none. **Tags and releases now run v26.9.0 → v26.9.3 with no gaps on both repos**, and `origin` carries only `main` now that the stale `wip/*` remotes are deleted. See [release history](context/release-history.md). (0) **DevHub polish — merged as PR #18** (squash `054e1a5`, 2026-09-15; `wip/docs-improvements` now deleted): an `MCP` nav link, `.btn--primary` re-skinned from mariadb.com's own button classes, and two hero-card fixes for narrow panels. See "DevHub polish" in [current state](context/current-state.md). (0) **The DevHub is merged and LIVE** at **https://ai-plugins.mariadb.com/** — PR #12 landed as `ed6fd43`, then #14, #15, and a custom domain (`docs/CNAME` + `baseurl: ""`). A static Getting Started site in `docs/`, served by GitHub Pages' built-in Jekyll from `main` + `/docs`. Ten tutorials, a filterable catalog, four learning paths, a generated skill catalog, an architecture page and an MCP tool reference. It also grew tooling that reaches outside `docs/`: `scripts/sync-skills.sh` now regenerates the site's skill data as its last step. See "DevHub (`docs/`)" in [architecture](context/architecture.md). (0) **Release 26.9.1 is out** (2026-09-08, tag `v26.9.1` = `4003d0d`, prerelease on both repos). It merged two independently-moved versions — the **mariadb-shell floor** (direct to `main`, `a693a28`) and the **plugin package version** (PR #11) — and shipped the repo-local **`mariadb-migrator`** skill (MySQL→MariaDB via the `migrator.*` MCP tools; new `additional-skills/migrator/` subfolder, dev plugins 75 → 76 skills), a skills re-vendor, a new **`CONTRIBUTING.md`** holding the maintainer docs, and README fixes. (a) **Codex now registers its own MCP server** — merged as PR #6; see Codex fact 5 in [architecture](context/architecture.md). (b) **`db.connect` coverage** on `wip/DB-CONNECT-TESTS`, which closed the last untested path an agent actually takes. (c) **PR transfers from the tracking fork** `MariaDB/ai-plugins` (remote `fork`) into `origin` — both of its PRs are transferred and merged (#9, #7). Earlier stream, merged:  rewrote the `mariadb-mcp-launcher.{sh,cmd}` scripts in all plugins to stop downloading release assets themselves and instead delegate to the shell's own `install.sh` / `install.ps1`; bumped the version gate to 26.8.0 (now explicitly a *minimum*); added a repo-root `LICENSE`, `.gitattributes` and `SECURITY.md`; restructured the main README (Installation moved directly under the harness table, new `## Plugin variants` heading, new "configure the MCP server" step propagated to all 7 MCP-bearing plugin READMEs); switched the install-facing org to **`mariadb`**; and added the GPL-2.0 copyright header to all 46 source files. Details in "Launcher rewrite" below.

`ai-plugins` packages MariaDB agent skills (+ the native `mariadb-shell` MCP server) as installable plugins for four coding agents: Claude Code (`claude/`), Codex (`codex/`), OpenCode (`opencode/`), and Pi/pi.dev (`pi/`). Each agent has `dev` (full skills + MCP), `sql` (SQL subset + MCP), `contributor` (skills-only) variants. Skills are vendored (never hand-edited) by `scripts/sync-skills.sh`. **This work stream** added a set of **MariaDB REST Service** skills (a fork of the MySQL REST Service) and **Schema Management (MSM)** lifecycle skills under `additional-skills/`, reorganized `additional-skills/` into `sql/`/`rest/`/`schema-management/` subfolders with per-plugin selection, added **two Claude e2e tests** that exercise the REST skills and the MSM lifecycle skills end-to-end (both pass), and updated the README. Latterly it also **unified how the tests run** across the plugins: a repo-root `run_tests.py` drives every suite with the Python inside `mariadb-shell` and one combined coverage report, and the `db` tier deploys its own sandbox instance instead of needing a server on 3306.

## Repo layout

| Path | What it is |
| --- | --- |
| `claude/`, `codex/`, `opencode/`, `pi/` | One dir per coding agent, each with `dev` / `sql` / `contributor` plugin variants plus its `*-plugin-test*` suite |
| `additional-skills/` | This repo's own skills, in `sql/` `rest/` `schema-management/` `migrator/` (+ `laravel/` on PR #28), plus the sources & licensing README |
| `docs/` | The DevHub — Jekyll site served by GitHub Pages, live at https://ai-plugins.mariadb.org/ (`.com` dropped on `wip/docs-uri-cleanup`) |
| `docs-ref/` | Reference docs: GitBook source in `content/` (for mariadb.com/docs, Enterprise Tools space) + Docusaurus preview; `npm run docs-ref` |
| `scripts/` | `sync-skills.sh` (vendors skills), `set-plugin-version.sh`, `set-mariadb-shell-version.sh` |
| `run_tests.py`, `pytest-coverage.ini` | Unified runner across every suite, one combined coverage report |
| `package.json` | The pi manifest (`pi` field; no dependencies since #37) + npm scripts |
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
| [`context/docs-ref.md`](context/docs-ref.md) | The `docs-ref/` reference docs: GitBook/preview split, plugin workarounds, content rules (passwords only at the prompt), next steps, build gotchas |

## Git state

`git status --short` at checkpoint time: only this checkpoint's `.claude/` edits
(`PROJECT_CONTEXT.md`, `context/{release-history,next-steps,files-that-matter}.md`),
uncommitted on `main`.

`git branch --show-current`: **`main`** = `origin/main` = `2a6ab29` (#41). No other
local branches; `origin` carries only `main` (`wip/skill-fixes` and
`wip/checkpoint-26.10.0` deleted). `fork/main` is at `68bd7d4` (#39), two
commits behind — synced at the next release.

**Open PRs**: none. Recently merged: **#41** `2a6ab29` (MSM skill fixes),
**#40** `7f0f593` (26.10.0 checkpoint), **#39** `68bd7d4` (release 26.10.0).

**Tags and releases run v26.9.0 → v26.9.5, then v26.10.0, with no gaps**, each an
annotated tag pushed to `origin` **and** `fork` as the same object, each a
**prerelease** on both repos.

Both remotes are present (`git remote -v`): `origin` =
`mariadb-corporation/ai-plugins`, `fork` = `MariaDB/ai-plugins`. See
[repo conventions](context/repo-conventions.md) for what each remote is for.
