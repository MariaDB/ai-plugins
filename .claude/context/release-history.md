# Release history

[← Project Context](../PROJECT_CONTEXT.md)

## Landed on `main` (through PR #18)

Landed on `main` since the last checkpoint, newest first: **#17** `12410f3` (MSM
e2e config-home fix), **#16** `d5e2bfc` (Release 26.9.2 — shell floor + plugin
version), `e8f532e` + `ee52550` (logo sizing), `d714648` (`baseurl` emptied for
the custom domain), `39b3c95` (`docs/CNAME`), **#15** `70daecc` (titled code
block as one panel), **#14** `7137a67` (sandbox brings its own server + a
version-comparison tutorial), **#13** `c5759e5` (mariadb-migrator split into an
overview + six topic skills), **#12** `ed6fd43` (**the DevHub**). So the long-open
PR #12 is merged and the "enable GitHub Pages" step is done — the site is live
at **https://ai-plugins.mariadb.com/**.

## Release v26.9.1 (2026-09-08)

- **Annotated tag `v26.9.1`** (tag object `2056cfa` → commit `4003d0d`), pushed to
  **both** `origin` and `fork` — the *same* object on each, verified with
  `git ls-remote --tags`, not two separately created tags.
- **Prerelease on both repos from the start**, unlike v26.9.0 which was published
  stable by mistake and edited afterwards: `gh release create v26.9.1 --repo <r>
  --title v26.9.1 --notes-file … --prerelease --verify-tag`. Notes are the tag
  annotation's body, extracted with `git tag -l --format='%(contents:body)'`
  because `gh` refuses `--notes-from-tag` together with `--repo`; both bodies
  checksummed identical afterwards.
- `releases/latest` still **404s** on both repos — every release is a prerelease
  and the endpoint excludes those. Nothing consumes it.
- Contents: the `mariadb-migrator` skill, the docs re-vendor, the plugin package
  bump to 26.9.1 (PR #11), and — merged earlier, direct to `main` — the
  `MARIADB_SHELL_VERSION` floor bump to 26.9.1 (`a693a28`).

## Release v26.9.0 (2026-09-02) — the repo's first tag and first release

- **Annotated tag `v26.9.0`** (tag object `5e360ac` → commit `80a4a6a`), pushed to
  **both** `origin` and `fork`; the same tag object, not two separately created
  ones. There were **no tags at all before this**, so 26.7.0 and 26.8.0 cannot be
  reached by tag name, and `v`-prefixed is now the convention (user's choice,
  matching `mariadb-shell`'s own `v26.9.0`/`v26.8.1` while the version *inside*
  this repo — manifests, CHANGELOG headings — stays bare `26.9.0`).
- **GitHub Releases published on both repos**, titled `v26.9.0`, notes taken from
  the tag annotation. Published **without** the prerelease flag by mistake and
  **flagged prerelease afterwards (2026-09-03)** with `gh release edit v26.9.0
  --repo <org>/ai-plugins --prerelease --verify-tag` — the flag *is* editable
  after publishing (only an **immutable** release is frozen; `gh release view
  --json isImmutable` says which, and both were `false`). Tag, title and the
  322-byte notes were untouched by the edit.
- **Consequence of that flag**, the same one `mariadb-shell` has:
  `repos/<org>/ai-plugins/releases/latest` **404s again** on both repos (verified
  after the edit) because the endpoint excludes prereleases — it had briefly
  resolved in the window when the release was stable. Nothing consumes it yet.

`main` history, newest first (PR merges are squashes, so branch SHAs do not
survive — check containment by **tree**, not by ancestry; `git rev-list ^main`
will report a merged branch's commits as missing):

- `4003d0d` — **`mariadb-migrator` skill + release 26.9.1** (PR #11), tagged
  `v26.9.1`. The skill covers MySQL→MariaDB migration with the `migrator.*` MCP
  tools; it lives in a new `additional-skills/migrator/` subfolder, so
  `sync-skills.sh`'s `ADDITIONAL_SUBDIRS` gained `"migrator"` — without that the
  file would never be vendored. Dev plugins 75 → **76** skills, sql unchanged at
  47. Also in it: skills re-vendored (docs `71f3ac5` — r2dbc 1.4.1 → 1.4.2;
  shell `33b4e3e` — nothing under `.claude/skills/` moved), the package version
  → 26.9.1 in 17 files, the `[26.9.1]` changelog cut in all 10 plugins, a new
  repo-root **`CONTRIBUTING.md`** holding the maintainer material that used to be
  the README's second `#` heading, and README fixes (every harness now points at
  the MCP-server config step; what `mcp setup` configures; sandboxes need a local
  MariaDB Server install).
- `a693a28` *(2026-09-08)* — **mariadb-shell floor → 26.9.1** via
  `scripts/set-mariadb-shell-version.sh 26.9.1`: 32 of its 35 candidate files
  changed — the 3 that did not are the **contributor plugins' READMEs**
  (`{claude,codex,opencode}/contributor-plugin/README.md`), which carry no version
  site because those variants are skills-only with no MCP server. Note also that
  `pi/dev-plugin/README.md` has only the JSON `env` site, not the prose
  `(default …)` one, so it moves by 1 line where the others move by 2.
  Pushed direct to `main`, no PR, **no CHANGELOG entry
  and no plugin-version bump** — the plugin package stays 26.9.0. `v26.9.1` was
  confirmed published (prerelease, 2026-09-07) *before* raising the floor, so the
  gate does not sit above the newest release. All 606 `test_structure.py` guards
  pass after the bump.
- `5bb6282` — PROJECT_CONTEXT only: `v26.9.0` flagged prerelease on both repos.
- `cf9601e` — PROJECT_CONTEXT only: the v26.9.0 release and the branch cleanup.
- `6e42fab` — **README restructured** (PR #7, fork PR 2 by @robertsilen): a
  `# Development and maintenance` rule splits maintainer material from user
  material, `## Configure the MCP server` promoted to H2, new `## What you can ask
  for`. Plus the Windows sandbox path (`%USERPROFILE%\MariaDB\mariadb-shell\sandboxes`,
  which is NOT the config home under `%APPDATA%`) and casing/formatting fixes.
- `3d8f8ea` — **Codex install commands corrected** (PR #9, fork PR 1 by @lefred):
  `/plugin` does not exist in Codex (the enum variant is `Plugins`), and `/plugins`
  takes no arguments (it browses interactively) while `/reload-plugins` does not
  exist at all — so all four Codex-facing READMEs now document the CLI
  (`codex plugin marketplace add …` / `codex plugin add …`), verified end to end.
  Claude Code keeps `/plugin`, which is correct there.
- `80a4a6a` — mariadb-shell floor → 26.9.0, changelogs cut as `[26.9.0]` (PR #10);
  tagged `v26.9.0`.
- `ac55729` — `db.connect` + `sandbox.deploy` connection coverage (PR #8).
- `014d574` — `sync-skills.sh` stops requiring a token: `mariadb-shell` is public,
  so the contributor plugins no longer drop out of an unauthenticated sync.
- `e6db430` — skills re-vendored (docs `ace4f63`, shell `2b2d0aa`); contributor
  plugins 1 → 2 skills (`review-shell-change`), their first sync in a while.
- `c5a3a8c` — **Codex registers its own MCP server** (PR #6): relative
  extensionless `command` + `"cwd": "."`, the `mariadb-mcp-launcher` shim, 4 static
  guards, and the 26.8.1 / 26.9.0 version bumps.
- `1615136` — pi test suite + `pi-test.yml` (PR #4).
- `5905134` — deleted the unread `.codex-plugin/marketplace.json`.
- `e89fac9` — Codex 0.147 fixes + codex e2e tier (PR #3).
- `86b6b7d` — plugin version 26.8.0, skills re-synced, `test_additional_skill_matches_its_source`.
- `fb08a4a` — LICENSE: dropped the Paramiko section (user's own commit).
- `1c4d422` — GPL-2.0 header on all source files + `SECURITY.md`.
- `b00fbc3` — install-facing org → `mariadb`.
- `735f74a` — launcher rewrite: delegate installing to the shell's
  `install.sh`/`install.ps1`; version gate as a *minimum*; `.gitattributes`.
- Below that, `7a52cc3` squashes the whole original `wip/AIPL-4` line (REST and MSM
  skills, the pi harness, `run_tests.py`, the db-tier sandbox); its 16 subjects are
  listed in that commit's own message.

Versions are two independent things, set by two scripts: plugin package
(`set-plugin-version.sh`, 17 files) and mariadb-shell floor
(`set-mariadb-shell-version.sh`, 35 candidate files, 32 of which actually carry a
version site — the 3 contributor-plugin READMEs have none, being skills-only).
Both are **26.9.1** as of the 26.9.1 release, but they got there **separately**:
the floor moved first, direct to `main` on 2026-09-08 (`a693a28`), and the
package version followed in PR #11 (`4003d0d`). They also coincided at 26.8.0 and at 26.9.0 (PR #10), and
were 26.9.0 vs 26.8.1 before that — coinciding is always a coincidence of
release timing, never a rule, so do not infer either from the other. Both
scripts take `--help` and refuse a non-version argument — before that,
`set-mariadb-shell-version.sh --help` wrote the literal string `--help` into all
35 files.
