# Release history

[← Project Context](../PROJECT_CONTEXT.md)

**Versioning policy (from 26.10.0, user's decision 2026-10-02): the plugin version and the
mariadb-shell floor are independent.** Through 26.9.5 every release set both to the same number
(the ai-plugins release matched a mariadb-shell release); that is no longer required. `/release
<version> [shell-version]` now checks the plugin version against this repo's tags and moves the
floor only when a shell version is given. 26.10.0 is planned on top of the current floor 26.9.5.
**Since #67 (2026-10-21)** both arguments are optional (`/release [version|-] [shell-version|-]`,
ported from the vscode-extension's `/release`): no version → the next `YY.MM.x` from today's date
and the month's tags; no floor → the latest published shell when it is newer than the floor.
Anything suggested is confirmed in one summary before anything changes.

## Landed on `main` (through PR #73)

**#73** `10f3095` (2026-10-22): **`videos/`** — a generated SE enablement video (2:11, MariaDB plc
style from `docs-ref/`), built from source: HTML animation captured in headless Chrome, local
Kokoro TTS narration, synthesized score/SFX. Tracked: `videos/{setup.sh,requirements.txt,README.md}`
and `videos/se-enablement/{PLAN.md,build.sh,src/}`; the toolchain cache, intermediates and the
rendered mp4/srt (`videos/output/`) are gitignored. Not part of any plugin; no CHANGELOG line.
See [current state](current-state.md) and `videos/se-enablement/PLAN.md`.
**#72** `3d84ff5` (2026-10-22): DevHub offline page gets direct download links (source archives
via a new `plugin_version` key in `docs/_config.yml`, shell packages + SHA256SUMS of the floor,
sandbox server packages from a new `docs/_data/downloads.yml`); `set-plugin-version.sh` sets
`plugin_version`; `/release` gains a step that updates the download links. The home page shows
"Version <plugin_version> · MariaDB Shell <shell_floor> or newer" under the hero badges.
**#71** `0be82e0` (2026-10-22): DevHub `/offline-install/` page for networks without GitHub
access (shell by hand, plugin from the release archive as a local marketplace, sandbox packages).
**#70** `6bc03e6` (2026-10-21): LICENSE names the extension "MariaDB Shell for VS Code"
(vscode-extension#8); same change in every repo sharing the file.
**#68** `6e63c80` (2026-10-21) was release 26.10.5 (below).
**#67** `4d90709` (2026-10-21): `/release` suggests the next version and the latest shell floor
(see the policy note above). The user remembered making this change here; it had only ever been
made in the vscode-extension repo (`49420be`, 2026-10-18), so it was ported, not restored.
**#66** `f54afd5` (2026-10-21): the **SQL language server** — floor → **26.10.3** (the first shell
with `mariadb-lsp`), `mariadb-lsp-launcher.{sh,cmd}` in claude/opencode/hermes dev+sql (Claude
`.lsp.json`, OpenCode `lsp` block, Hermes README snippet), extensionless launchers so Claude Code
and OpenCode work on native Windows, the MCP-timeout hint, `sql.*` tool docs. It raised the floor
on `main` without a CHANGELOG line for it; the 26.10.5 CHANGELOGs carry that line.
**#65** `473389b` (2026-10-21): `docs-ref/scripts/generate-skill-pages.py` code-quotes a word
holding a `<placeholder>` and escapes `*` in skill descriptions (they rendered as
`development/_next.sql`, `auto//scripts/_norecord.py`, stray italics), and now writes #64's
SYNCED comment and GPLv2 footer itself — every regeneration used to delete them. New
`docs-ref/content/.markdownlint.jsonc` (MD013/MD031/MD036 off, MD024 `siblings_only`, MD033
`<sub>` only, MD049 underscore; body `*x*` → `_x_`). Preview HTML byte-identical except the
three generated pages that were wrong.
**#64** `848bd08` (2026-10-20): a SYNCED warning comment (below the H1) and the docs team's
`<sub>_This page is licensed: GPLv2_</sub>` footer on every synced docs-ref page.
**#63** `b9949ef`: language fixes on the util tools page.
**#62** `9d38919`: one third-party LICENSE list shared by mariadb-shell, mariadb-shell-plugins,
lsp-server, vscode-extension and ai-plugins.
**#61** `fc3e9bf`: MSM skills — `SOURCE` slices by line number (`lnN`), no slice for a whole
file (mariadb-shell-plugins #60); shells ≤ 26.10.2 still need character offsets.
**#60** `c98c925` / **#59** `9728ee1`: the DevHub follows mariadb.org's new theme
(twentytwentyfive-child palette, header/footer, scroll-to-top button).
**#58** `de794e4`: docs for the MCP server's `util.*` group (DevHub + new docs-ref page).
**#57** `f5fbe88`: checkpoint after release 26.10.4.
**#56** `2a90ebf` (2026-10-19) was release 26.10.4 (below).
**#55** `67d3424` (2026-10-18) added the **CLI guard**: every MCP-bearing plugin blocks a shell
command that uses `mariadb`/`mysql`/`mariadb-shell`/`mysqlsh`/`mariadb-dump` for what an MCP
tool covers and names the tool instead (`MARIADB_PLUGIN_ALLOW_CLI=1` turns it off) — a
`PreToolUse` hook in Claude Code and Codex, the extension in Pi, `plugins/mariadb-guard.ts` in
OpenCode, and a new separate **`hermes/guard-plugin`** (`mariadb-guard`, the 14th plugin, with
its own CHANGELOG; `set-plugin-version.sh` now updates its `plugin.yaml`). One case list,
`tests/cli-guard-cases.json`, drives all three implementations. `56a9629` made `/release` ask
before keeping the floor when a newer shell exists. **#53** `2206a90` was the 26.10.3 checkpoint.
**#52** `43a33cb` (2026-10-15) was release 26.10.3 (below).
**#51** `4747939` (2026-10-15) moved `docs-ref/content/mariadb-ai-plugins/` to
`content/community/mariadb-ai-plugins/` (mariadb.com/docs now lists the plugins under
Community Tools, `tools/community/`), with a Community Tools landing stand-in and a
regenerated Skills Reference page #50 had left stale. **#50** `6976f16` moved the five REST
skills to the shell's built-in `mrs` module and metadata schema 5.0.0 (`mariadb_rest_service`,
`VENDOR MARIADB`, `rest_object`), Hermes copies included after the rebase on #47. **#49**
`00e22c7` documented the MCP server's `rest.*` tools in docs-ref. **#48** `dac9f78` made the
docs-ref preview check anchors and descriptions the way GitBook does. **#47** `ee00bf4` added
**Hermes Agent** as the fifth harness (`hermes/{dev,sql,contributor}-plugin`, test suite, CI,
docs), the launcher's download-then-run hint, and the `mysql://` test/doc fixes; after the
upstream skill fixes (mariadb-docs#1271, MariaDB/skills#31) it re-vendored to mariadb-docs
`cc8dd40` / mariadb-shell `37cb1d3` and dropped `--force` from every Hermes install (the
install scan now passes all three plugins; the e2e installs without it). **#45** `5660e22` was
the 26.10.2 checkpoint. **#46** (GitHub Copilot in VS Code, docs only) is still open.

**#44** `13685aa` (2026-10-09) was release 26.10.2 (below); it also made `/release` parse `$ARGUMENTS` itself. **#43** `f06db43` (2026-10-09) was the 26.10.1 checkpoint. **#42** `2574a74` (2026-10-08) was release 26.10.1 (below). **#41** `2a6ab29` (2026-10-06) corrected the MSM section rules in the schema-management
skills (250 never deployed → views/routines in 150, removals in 240; 270 only `REVOKE`/`DROP ROLE`,
grants in 170; `SOURCE` needs a slice), their vendored copies, the MSM e2e tests, `docs-ref` and the
DevHub, with `[Unreleased]` CHANGELOG entries. It also carried two `.claude/commands/` commits:
a new `/read-checkpoint` (`991e38b`) and `/checkpoint` without the `$1` target-subfolder argument
(`b354f57`). **#40** `7f0f593` was the 26.10.0 checkpoint. Shipped in 26.10.1.

**#39** `68bd7d4` was release 26.10.0 (below); **#38** `f2ceecb` decoupled the plugin version
from the shell floor in `/release` (see the policy above).

**#37** `5711b11` moved the Pi plugin to Pi 1.0's built-in MCP: the extension registers the
`mariadb` server itself (`pi.registerMcpServer`), `pi-mcp-adapter` and the setup script/command are
gone, docs carry a migration section, and the pi e2e makes a real MCP call. Unreleased — the
Pi CHANGELOG has it under `[Unreleased]`.

**#36** `0d77b1e` put everything the reader types in `docs-ref/content/` into code fences
with a language (reviewer feedback), and fixed the `mcp.setup()` note (SQL-mode start, `\py`, no
JS mode). Fork fast-forwarded to it by the user.

**#35** `17bce4b` added `docs-ref/`, the GitBook reference docs with an offline Docusaurus
preview (see [reference docs](docs-ref.md)); **#34** `4e2e6d5` corrected the DevHub's claim that
`db.execute_sql_script` gives each statement a fresh session, and updated the favicons.

**#33** `c084a21` rebuilt the DevHub header and footer on mariadb.org's;
**#32** `81f72fa` moved the DevHub palette to mariadb.org's blues with its
space banner; **#31** `25d19ad` was the 26.9.5 checkpoint.

**#30** `dec6f52` was release 26.9.5 (below); **#29** `2e83366` made the
DevHub `.org`-only; **#28** `9eb9119` added the Laravel skills.

**#25** `5d07abf` added the **`/release <version>` command**
(`.claude/commands/release.md`): checked the version was the newest mariadb-shell
release (until the versions were decoupled for 26.10.0 — see the policy above), ran the three scripts, CHANGELOG, static tests, checkpoint, PR; after
the merge, tag + prereleases on both repos and a merge-based fork sync that
keeps the fork's `docs/CNAME`. **#26** `2bbdb2a` was release 26.9.4, the first
cut with that command (below). **#24**/**#23**
recorded the `.org` fork domain; **#22** rewrote the tutorials; **#21** was the
26.9.3 checkpoint.

**#20** `b6ed467` was release 26.9.3 (below). **#19** `1732462` split this context
set out of a single 84KB `PROJECT_CONTEXT.md`
(the line count hid the size — 340 lines at ~250 chars each), and rewrote
`/checkpoint` to take a target subfolder and detect three layouts. **#18**
`054e1a5` was the DevHub polish. No PR is open, and `origin` now carries only
`main` — the stale `wip/*` remotes are deleted.

**#19** `1732462` split this context set out of a single 84KB `PROJECT_CONTEXT.md`
(the line count hid the size — 340 lines at ~250 chars each), and rewrote
`/checkpoint` to take a target subfolder and detect three layouts. **#18**
`054e1a5` was the DevHub polish. PR **#20** (release 26.9.3) is open.

Landed on `main` since the last checkpoint, newest first: **#17** `12410f3` (MSM
e2e config-home fix), **#16** `d5e2bfc` (Release 26.9.2 — shell floor + plugin
version), `e8f532e` + `ee52550` (logo sizing), `d714648` (`baseurl` emptied for
the custom domain), `39b3c95` (`docs/CNAME`), **#15** `70daecc` (titled code
block as one panel), **#14** `7137a67` (sandbox brings its own server + a
version-comparison tutorial), **#13** `c5759e5` (mariadb-migrator split into an
overview + six topic skills), **#12** `ed6fd43` (**the DevHub**). So the long-open
PR #12 is merged and the "enable GitHub Pages" step is done — the site is live
at **https://ai-plugins.mariadb.com/**.

## Release v26.10.6 (2026-10-24) — IN PROGRESS (PR about to open)

- Bare `/release`: version **26.10.6** suggested (tags up to `v26.10.5`), floor **26.10.3 →
  26.10.4** suggested (mariadb-shell `v26.10.4`, published 2026-10-24 06:26 UTC, built from
  `b074605`). User confirmed both. Branch `wip/26.10.6` off `ba71d8a`.
- `9c84891` floor → 26.10.4 (**55 files**, up from 39 at 26.10.4: #66 added 12 `mariadb-lsp`
  launchers, 2 `.lsp.json` and 2 docs-ref pages; `/release`'s reference counts updated).
  `e90e2a1` plugin version → 26.10.6 (**26 files**, incl. `plugin_version` in `docs/_config.yml`).
- `8f39cbb` re-vendor, **provenance only** (13 `skills-source.json`): mariadb-docs `12d4cd3` →
  `62ef6fe`, mariadb-shell `1413abd` → `b074605`. Counts 85 / 47 / 3.
- DevHub download links: `downloads.yml` unchanged — the newest sandbox packages at or below
  26.10.4 are still `v26.10.0` (11.8.9, 12.3.3, 13.1.1); `v26.10.4` has all six platform
  packages + `SHA256SUMS`. All offline-page links 200 except the `v26.10.6` archive/tag links
  (404 until the tag is pushed). No local shell at 26.10.4 to cross-check the index.
- `5368d89` CHANGELOGs (fourteen): #70's LICENSE rename (all fourteen), the floor line in the
  nine MCP-bearing plugins, the re-vendor, the version bump. No `[Unreleased]` sections.
  #71–#73 touch no plugin.
- Static tier green: claude 830, codex 811, hermes 904, opencode 689, pi 693.

## Release v26.10.5 (2026-10-21) — SHIPPED

- **PR #68**, squash `6e63c80` (merged head `025fd13`, checkpoint included). **Annotated tag
  `v26.10.5` = object `af5dc47`**, pushed to `origin` and `fork` as the same object;
  **prerelease on both repos**. Fork's `main` fast-forwarded `c98c925` → `6e63c80` (=
  `origin/main`). `wip/26.10.5` deleted locally; GitHub had removed it on `origin`.
- Tag subject is `Release 26.10.5`, not the `MariaDB AI Plugins 26.10.x` of earlier tags — left as
  is rather than force-push a published tag. Use `MariaDB AI Plugins <version>` next time.
- Tag notes: floor 26.10.2 → 26.10.3 (vs. v26.10.4), the SQL language server, native-Windows
  launchers, the MSM `SOURCE` slice change, LICENSE, provenance-only re-vendor.
- The fork sync's `git fetch fork origin` (two remotes without `--multiple`) failed; the chain
  still pushed `main` = `origin/main` to `fork` as a fast-forward, the intended result.

- The first bare `/release` (#67): version **26.10.5** suggested (tags `v26.10.0`–`v26.10.4`),
  floor **26.10.3** kept — already on `main` since #66 and the newest shell (`v26.10.3`,
  2026-10-20). User confirmed the summary. Branch `wip/26.10.5` off `4d90709` (#67).
- No floor script run (floor already at target). `e4cdee3` plugin version → 26.10.5 (**25 files**,
  same as 26.10.4).
- `e8ba295` re-vendor, **provenance only** (13 `skills-source.json`): mariadb-docs `a439473` →
  `12d4cd3`, mariadb-shell `a4352a5` → `1413abd`. Counts 85 / 47 / 3.
- `8053417` CHANGELOGs (fourteen): `[Unreleased]` (#66 LSP + Windows launchers + MCP-timeout hint,
  #62 LICENSE) folded into `[26.10.5]`; the floor line **26.10.3** in the nine MCP-bearing plugins
  (moved since v26.10.4, by #66); #61's `mariadb-schema-management-develop` change (optional
  `SOURCE` slice, `lnN` bounds) in the five dev plugins, which #61 had left without an entry.
- Static tier green: claude 830, codex 811, hermes 904, opencode 689, pi 693.
- Note: the first draft of the re-vendor commit message swapped the two upstream commits
  (`git diff` lists `claude/contributor-plugin` before `claude/dev-plugin`); amended before push.

## Release v26.10.4 (2026-10-19) — SHIPPED

- **PR #56**, squash `2a90ebf` (merged head `d3805c2`, the checkpoint commit included this
  time). **Annotated tag `v26.10.4` = object `cca0c4e`**, one-line subject so the summary is all
  in `%(contents:body)`, pushed to `origin` and `fork` as the same object; **prerelease on both
  repos**. Fork's `main` fast-forwarded `2206a90` → `2a90ebf` (= `origin/main`, diff empty).
  `wip/26.10.4` deleted locally (head = `headRefOid`); GitHub had removed it on `origin`.
- Tag notes state the floor move to 26.10.2, the CLI guard (incl. `mariadb-guard` for Hermes)
  and the re-vendor.
- **`/release` updated for the guard plugin** (on the checkpoint PR #57): fourteen CHANGELOGs (the
  `skills-source.json` files stay thirteen — the guard vendors no skills), the guard's section is
  a version bump alone when nothing in it changed, and the file-count reference now names
  26.10.4's 39 / 25.

- `/release 26.10.4`, no floor given, but **mariadb-shell `v26.10.2` was published 2026-10-17**
  (built from `a4352a5`), so the command asked and the user chose **floor 26.10.1 → 26.10.2**.
  Branch `wip/26.10.4` off `67d3424` (#55).
- `d6f430e` floor → 26.10.2 (**39 files**: 31 + 8 Hermes). `114d17c` plugin version → 26.10.4
  (**25 files**: 23 + the guard plugin's `README.md` and `plugin.yaml`).
- `26ba6d4` re-vendor (17 files): mariadb-docs `cc8dd40` → `a439473` with nothing under
  `agent-skills/` changed; mariadb-shell `37cb1d3` → `a4352a5`, **`review-shell-change`** changed
  (§1.1 unreachable scenarios are not findings; §7 out-of-change defects go to a follow-up list)
  in the four contributor plugins. Counts 85 / 47 / 3.
- `397c6ac` CHANGELOGs, now **fourteen** (`hermes/guard-plugin` is new): #55's `[Unreleased]`
  CLI-guard entries folded into `[26.10.4]`, the guard plugin's first release, the floor line in
  the nine MCP-bearing plugins.
- Static tier green: claude 807, codex 811, hermes 902, opencode 689, pi 693 (JUnit counts;
  the guard tests from #55 raised them).

## Release v26.10.3 (2026-10-15) — SHIPPED

- **PR #52**, squash `43a33cb` (merged head `dfb77b9`). **Annotated tag `v26.10.3` = object
  `65b8865`**, pushed to `origin` and `fork` as the same object; **prerelease on both repos**,
  bodies identical. The tag has a one-line subject (`MariaDB AI Plugins 26.10.3`) so the whole
  summary lands in `%(contents:body)` — v26.10.2's first paragraph had become its subject and
  is missing from that release's notes. Fork's `main` fast-forwarded `13685aa` → `43a33cb`
  (= `origin/main`, diff empty).
- **The PR was merged before `3ba3ecc` (the "PR open" checkpoint, with the two new gotchas)
  reached it**, so `wip/26.10.3` on `origin` ends one commit past the merged head; that commit
  was cherry-picked onto `wip/checkpoint-26.10.3`. Per the deletion rule the branch is kept
  until the user decides.

- `/release 26.10.3`, no floor: it stays **26.10.1**, still the newest mariadb-shell release
  (2026-10-08). Branch `wip/26.10.3` off `4747939` (#51).
- `2e2876c` plugin version → 26.10.3 (**23 files**: 17 + 6 for Hermes, as expected).
- Re-vendor changed **nothing** — upstream heads are still mariadb-docs `cc8dd40` and
  mariadb-shell `37cb1d3`, which #47 already vendored — so no commit for that step. But those
  commits are new since v26.10.2 (`8bb700f` / `43338f8`), so the CHANGELOGs record them: the
  Connector/C, C++, ODBC, Python install skills and `mariadb-features` no longer run `sudo`
  (root steps handed to the user; `$HOME/.local` builds; per-user ODBC registration; venv;
  `lib64/mariadb` for RPM tarballs) — dev; only `mariadb-features` in sql; contributor's
  `create-shell-plugin` line ref + dropped `plugins_path` note. Counts 85 / 47 / 3.
- `02f2756` CHANGELOGs: the `[Unreleased]` sections (launcher hint, REST 5.0.0, REST fixes)
  folded into `[26.10.3]`; no floor line (floor didn't move); the **Hermes plugins' first
  release** — their `[Unreleased]` became `[26.10.3]`, with the vendored commits corrected from
  `8bb700f`/`43338f8` to `cc8dd40`/`37cb1d3`.
- Static tier green: claude 682, codex 686, hermes 779, opencode 682, pi 691.
- `dfb77b9` checkpoint. **PR #52** ("Release 26.10.3: plugin version, CHANGELOGs, and
  Hermes Agent's first release"; no `[bypass-ci]`, manifests in the diff).

## Release v26.10.2 (2026-10-09) — SHIPPED

- Asked for as `/release 26.10.2 26.10.2`, but **mariadb-shell has no v26.10.2**: the newest is
  `v26.10.1` (published 2026-10-08 19:49 UTC), so the user chose **floor → 26.10.1** (plugin
  version 26.10.2 as asked). The 26.10.1 checkpoint PR #43 was merged first, at the user's
  hand, so the branch is off `f06db43`.
- **PR #44**, squash `13685aa`. **Annotated tag `v26.10.2` = object `a648c37`**, pushed to
  `origin` and `fork` as the same object; **prerelease on both repos**, bodies sha256-identical
  to the annotation. Fork's `main` fast-forwarded `2574a74` → `13685aa` (= `origin/main`, diff
  empty). `wip/26.10.2` deleted locally, already gone on `origin` (GitHub removes it at the merge).
- Branch `wip/26.10.2`, one commit per step: `fab5412` floor → 26.10.1 (31 files), `83f789c`
  plugin version → 26.10.2 (17 files), `895aee7` re-vendor (31 files), `df01926` CHANGELOGs,
  `58123a6` checkpoint, `fe1027a` the `/release` `$ARGUMENTS` fix (see gotchas).
- **Re-vendor shipped content again**: mariadb-docs `b00b9f3` → `8bb700f`, mariadb-shell
  `70a9ff5` → `43338f8` (provenance only, 3 contributor skills unchanged). Three skills changed
  in dev AND sql (21 files + 10 `skills-source.json`): `mariadb-numeric-functions` corrects
  division by zero (NULL in a query, warning 1365 under `ERROR_FOR_DIVISION_BY_ZERO`, an error
  only when writing a row under strict mode; the old text named a non-existent
  `ERROR_ON_DIVISION_BY_ZERO`), `mariadb-control-flow-functions` a typo in `IFNULL`,
  `mariadb-lock-tables` only its last-updated date. Counts 85 / 47 / 3; `skills.yml` unchanged.
- No `[Unreleased]` sections to fold. The seven MCP-bearing CHANGELOGs carry the floor line.
- Static tier green: claude 682, codex 686, opencode 682, pi 691.
- Tag notes state the floor move and the three re-vendored skills.

## Release v26.10.1 (2026-10-08) — SHIPPED

- **PR #42**, squash `2574a74`. **Annotated tag `v26.10.1` = object `9bcbd39`**, pushed to
  `origin` and `fork` as the same object; **prerelease on both repos**, bodies sha256-identical
  to the annotation (trailing whitespace stripped). Fork's `main` fast-forwarded `68bd7d4` →
  `2574a74` (= `origin/main`, diff empty). `wip/26.10.1` deleted locally; GitHub had already
  removed it on `origin` at the merge (only the stale tracking ref needed pruning).
- Branch `wip/26.10.1` off `1c433bb` (#41's checkpoint merge), seven commits, one per step:
  `7494ae8` floor → 26.10.0 (31 files; 33 at 26.9.5 minus the two Pi files #37 removed),
  `9ad453b` plugin version → 26.10.1 (17 files), `48e5f9f` re-vendor, `296e07f` CHANGELOGs,
  `07c530c` checkpoint, `d8f1349` a multi-tenant note in both MCP tool references (see below),
  `b1e6e9e` checkpoint fix.
- **First release since 26.9.5 that moves the shell floor**: mariadb-shell `v26.10.0` was
  published 2026-10-08 (prerelease, the newest), so `set-mariadb-shell-version.sh 26.10.0` ran
  first. Plugin version 26.10.1 (highest tag before it: `v26.10.0`).
- **Re-vendor shipped content**: mariadb-docs `8781534` → `b00b9f3` (`ref` back to `main`
  from the pinned commit #41 synced at), mariadb-shell `874ad63` → `70a9ff5` (provenance
  only, 3 contributor skills unchanged). Seven function-reference skills changed in dev AND
  sql (49 files + 10 `skills-source.json` = 59): upstream's extractor now keeps multi-line
  signatures whole (all window functions, `TO_DATE`, `JSON_TABLE`), strips GitBook tab markup
  (`SESSION_USER`, `TO_CHAR`), fixes `AES_DECRYPT`'s signature and extracts six functions it
  used to skip (`MONTHS_BETWEEN`, `SFORMAT`, `VEC_FromText`, `VEC_ToText`, `PERCENTILE_CONT`,
  `PERCENTILE_DISC`). Counts unchanged, 85 / 47 / 3; `docs/_data/skills.yml` unchanged.
- **Ships #41** (MSM section-rule fixes): the four dev-plugin `[Unreleased]` sections folded
  into `[26.10.1]` as `### Fixed`. All ten CHANGELOGs got the re-vendor + version entry; the
  seven MCP-bearing ones also the floor line.
- Static tier green: claude 682, codex 686, opencode 682, pi 691 (same as 26.10.0).
- **mariadb-shell 26.10.0 is the first with the MCP server's multi-tenant mode** (mcp_plugin
  PR #37, `a5ad8bdf`, 2026-10-07). Checked against this repo on 2026-10-08: tool names and
  counts unchanged (8 / 12 / 8 + 4); the launchers' stdio start is unaffected (a server
  configured `--multiTenant=true` refuses stdio with a clear error, so nothing to handle);
  the new `--toolNameSeparator` defaults to `.`, which is what every doc and skill names.
  The one doc gap: a multi-tenant server serves only `db` and `msm`, so one paragraph was
  added under the group table of `docs/mcp-tools.md` and `docs-ref/.../mcp-tool-reference/README.md`
  (user's call: nothing more about the mode, the plugins launch the server themselves).
- Tag notes state the floor move (first shell with multi-tenant mode; launchers unchanged), the MSM
  skill fixes, and the content re-vendor.

## Release v26.10.0 (2026-10-02) — SHIPPED

- **PR #39**, squash `68bd7d4`. **Annotated tag `v26.10.0` = object `ed68f6a`**, pushed to
  `origin` and `fork` as the same object; **prerelease on both repos**. Fork's `main`
  fast-forwarded to `68bd7d4` (tree = `origin/main`). `wip/26.10.0` deleted (GitHub had
  already removed it on `origin`).
- Tag notes state the floor (26.9.5, not moved), the decoupling, the Pi 1.0 change with its
  migration steps, and the provenance-only re-vendor.
- **First release with the plugin version decoupled from the shell floor** (#38): plugin
  version → 26.10.0 (`set-plugin-version.sh`, 17 files), **floor stays at 26.9.5**
  (`set-mariadb-shell-version.sh` not run; `v26.9.5` is still the newest mariadb-shell release,
  published 2026-09-29).
- **Re-vendor, provenance only**: mariadb-docs `3a0974f` → `8781534` with nothing under
  `agent-skills/` changed; mariadb-shell `.claude/skills` still `938d473`. Counts 85 / 47 / 3.
- **Ships #37** (Pi 1.0 built-in MCP): Pi's `[Unreleased]` CHANGELOG section folded into
  `[26.10.0]`. The other nine CHANGELOGs got a re-vendor + version entry; the MCP-bearing ones
  also say the plugin version no longer follows mariadb-shell's numbers and the floor stays at 26.9.5.
- Static tier green: claude 682, codex 686, opencode 682, pi 691.

The 26.9.x release notes (v26.9.0 → v26.9.5) are in [release-history-26.9.md](release-history-26.9.md).
