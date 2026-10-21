# Reference docs (`docs-ref/`)

[← Project Context](../PROJECT_CONTEXT.md)

GitBook reference docs for the plugins, merged as **PR #35** (`17bce4b`,
2026-10-01). Target: the **Community Tools** section of the Enterprise Tools space of
mariadb.com/docs (`tools/community/` in `mariadb-corporation/mariadb-docs`, next
to the MySQL to MariaDB Migrator; moved there from `tools/` on 2026-10-15). `docs-ref/README.md` is
the maintainer guide (preview, writing rules, porting steps); this file holds
what is NOT in it.

## Architecture

- **`content/` is GitBook source, ported unchanged**; everything else in
  `docs-ref/` is the Docusaurus 3.10 preview (`docusaurus-plugin-gitbook`
  1.0.6). `content/README.md` and `content/community/README.md` are
  stand-ins for the Enterprise Tools and Community Tools landings — only their
  `MariaDB AI Plugins` sections are for porting. Product pages live in
  `content/community/mariadb-ai-plugins/`.
- **`content/SUMMARY.md` is the only page tree**: `sidebars.js` parses it
  (`* [Title](path.md)`, 2-space indent; an entry with children → category
  linked to its own page). Never hand-maintain a Docusaurus sidebar.
- **Images live in `content/.gitbook/assets/`** (GitBook's place), referenced
  relatively (`../../.gitbook/assets/x.svg` from the product root) so they resolve in
  `tools/community/` too. NOT
  `static/img/` — that is preview-only (logos, favicons, root redirect).
- **URLs mirror mariadb.com/docs**: `baseUrl` `/docs/`, `routeBasePath`
  `tools` → `/docs/tools/community/mariadb-ai-plugins/…`. `trailingSlash: true` so every
  page is `<page>/index.html` (plain Apache/nginx). `DOCS_BASE_URL` overrides
  the base path. A postBuild plugin writes `build/.htaccess`
  (`ErrorDocument 404 <base>404.html` only).
- **`src/remark/gitbook-extras.js`** fills plugin gaps without patching it:
  `remarkGitBookPrepare` renames `content-ref` → `contentref` (the plugin's
  tokenizer only takes `\w+` tag names); a `contentref` transformer + card
  renderer that titles cards from the target page's H1; every registered
  transformer is wrapped to get the block's full inner source (the plugin's
  `columns` transformer reads only `child.content` and drops nested blocks);
  frontmatter `description` → lead paragraph; dir links → `README.md`. Order
  matters: `beforeDefaultRemarkPlugins: [prepare, remarkGitBook, extras]`.
- **Theme** (`src/css/mariadb-gitbook.css`): colour scales copied from the live
  site's `--primary-*`/`--tint-*` custom properties (light + dark); type scale
  **measured** with headless Chrome over CDP on live Connector/Python pages
  (H1 36/45 700, H2 30/37.5 600, H3 24/33 600, body 16/26, chrome 14/20,
  breadcrumbs 12/16, tables 14/20 + th 500 + 8px 12px). `src/theme/Navbar`
  wraps the navbar with the space-tab row.
- **Skills Reference pages are generated** by `scripts/generate-skill-pages.py`
  from `docs/_data/skills.yml` + each `SKILL.md` description (text before
  "Use when"); page intros live IN the generator. Rerun after
  `scripts/sync-skills.sh` (`npm run docs-ref:skills`).

## Content rules settled with the user

- **Passwords are only ever entered at the `mcp setup` prompt.** No docs page
  shows `--password`, `--passwordEnv`, `--passwordStdin`, or a password in a URI;
  Command Line Configuration omits those three options and says why.
- **Plain technical-writer prose** (mariadb-docs style guide): no colon-led
  lists in descriptions, no rhetorical one-liners, no "not X, but Y", no
  fragments; Title Case headings; `description:` on every page. The DevHub
  keeps its own conversational voice.
- **Facts come from source, not from the DevHub**: `~/git/mariadb-shell`
  (URI grammar, connection options, SSH code) and
  `~/git/mariadb-shell-plugins/mcp_plugin` (tools, setup). Nothing
  `--gui`-specific (the VS Code extension's mode) goes in.
- **Anything the reader types goes in a code fence with a language** (reviewer
  feedback, PR #36 `0d77b1e`): `bash` for shell, `batch` for Windows cmd,
  `sql`, and `text` for agent prompts, slash commands (`/plugin`, `/reload`),
  URIs and sample output. No bare ```` ``` ````. One fence per prompt (Basic
  Usage's examples are fences, not italic bullets), no backticks inside a
  `text` fence. Commands only *named* in prose (`configured with mcp setup`)
  stay inline; so do commands in table cells (a cell can't hold a fence).
- **MariaDB Shell starts in SQL mode and has no JavaScript mode** (user,
  2026-10-02): an interactive `mcp.setup()` needs `\py` first; fence it as
  `python`, never `js`.

## Current state

- 42 pages: About, Installation (4 harnesses), Configuring the MCP Server group
  (Database Accounts, Adding Database Connections, Tunnel via SSH, Command Line
  Configuration), Basic Usage, Plugin Variants, Features (SQL Script Creation
  and Execution, Sandbox Instances, MSM, REST, MySQL migration), Architecture
  (with the user's `MariaDB_AI-Plugins_Architecture.svg`), Security Model,
  Skills Reference (7 generated), MCP Tool Reference (5), Configuration
  Reference, Troubleshooting, Release Notes, License, Bug Reports.
- **No `rest.*` / `restd.*` / `mrs.*` docs, on purpose** (user, 2026-10-19).
  `rest-tools.md` (from #49) and the DevHub's `rest.*` section were removed in
  #58, with the REST Daemon sentences in `sandbox-tools.md`. Reason: in
  mariadb-shell-plugins the groups are being renamed before the daemon group's
  first release — the REST Service group `mrs` → **`rest`** (15 tools,
  shipped as `mrs.*` in shell 26.10.2) and the REST Daemon group `rest` →
  **`restd`** (7 tools, incl. `get_certificate_status` / `trust_certificate`,
  never released). Document both once a shell release ships the new names;
  #49's text in git history (`00e22c7`) is a starting point for `restd`, but
  it predates the certificate tools and still says "self-signed".
- **`util-tools.md`** (12 tools, `mcp_plugin/lib/util_functions.py`,
  `tasks.py`, `util_process.py`) ships in **shell 26.10.2**, the floor, so
  `util.*` is IN the count: 28 → 40, "four groups" (DevHub `tool_count`,
  README, both architecture pages, both tool references). It was missed for a
  week because #55 (CLI guard) pointed agents at `util.copy_*` without touching
  docs. **How to tell what a shell release ships**: the shell's release
  workflow builds from the plugins' `release/candidate` branch, whose `VERSION`
  names the release — check `git merge-base --is-ancestor <commit>
  origin/release/candidate`.
- **Multi-tenant mode serves only `db.*` from shell 26.10.2 on** (plugins
  `f1b3b6e2`, #42); 26.10.0/26.10.1 also served `msm.*`. Both tool references
  say so.
- Verified: clean build (fails on broken links / missing content-ref targets),
  static tests pass, no horizontal overflow at 390px, Apache 2.4 serving
  `/docs/` (pages, 301 to slash, 404 page, `AllowOverride FileInfo`).
- The connection-error table was captured on a sandbox via
  `shell.open_session()`; `db.execute_sql_script` session behaviour verified
  through the real MCP server (see gotchas.md).

## Next steps

1. **Generate the MCP Tool Reference from the plugin's docstrings.** Only
   `sandbox.*` and `db.execute_sql_script` were checked against
   `mcp_plugin/lib/*_functions.py`; `db`/`msm`/`migrator` args still come from
   the DevHub.
2. **Port to mariadb-docs** per `docs-ref/README.md` (copy into
   `tools/community/`, merge SUMMARY + landing sections, cross-space links → `{server}/…` aliases,
   run `docs-check`).
3. Unverified on the pages: an end-to-end SSH tunnel (no SSH host here); error
   1130 (not reproducible on a sandbox — MariaDB's documented text is used); a
   TLS-failure row was dropped because the sandbox accepted `ssl-mode=REQUIRED`.
4. (Optional) Agent-style skill descriptions in the Skills Reference tables
   are quoted verbatim — improve them in the skill sources, not here.

## Gotchas

- **`"type": "module"` in `docs-ref/package.json` breaks the build**
  (`require.resolveWeak is not a function`). Leave it out; Docusaurus loads the
  ESM config through jiti anyway.
- The plugin serializes a link whose text equals its URL as plain text — that
  is exactly GitBook's `[x.md](x.md)` content-ref body, so the card renderer
  falls back to the block's `url=`.
- **An empty static directory fails the build** → `content/.gitbook` is only
  added to `staticDirectories` once it holds a non-dot file.
- `editUrl` is joined with the path relative to the SITE dir, so it must be
  `…/edit/main/docs-ref/`, not `…/docs-ref/content/` (gave `content/content`).
- **Infima overrides heading sizes** (`.markdown h1:first-child` 3rem,
  `.markdown > h2` 2rem) — set px on `.theme-doc-markdown.markdown hN`, not the
  `--ifm-hN-font-size` variables.
- `table { display: table }` kills Infima's mobile scroll wrapper → apply it
  only ≥997px.
- **No `DirectoryIndex` in `.htaccess`**: it needs `AllowOverride Indexes`,
  and a server allowing only `FileInfo` answers every request with a 500.
- Headless Chrome screenshots: `--blink-settings=preferredColorScheme=1` for
  light (0 = dark). CDP from Node 24's global `WebSocket` works without
  puppeteer (scripts were in the session scratchpad, not kept).
- `mcp setup --help` needs the REAL config home (an empty
  `MARIADB_SHELL_USER_CONFIG_HOME` has no plugins → "no object registered
  under name 'mcp'").
- **Inactive GitBook tabs aren't in the static HTML** (the Windows tab of
  Codex/Configuring): they render client-side, so grep `build/assets/js`, not
  the page's `index.html`, to check their content. Built pages live at
  `build/tools/community/…` (no `docs/` dir in `build/`).
- Prism `batch` must be in `additionalLanguages` (added in #36) or Windows
  fences render unhighlighted.

## Markdownlint (since #65)

`content/.markdownlint.jsonc` holds the folder's exceptions, each with its reason: MD013 off (GitBook writes one line per paragraph; tables can't wrap), MD024 `siblings_only` (the landing page repeats its H1 as an H2), MD031 off (GitBook puts fences directly inside `{% tab %}`; the user chose this over adding blank lines), MD033 `<sub>` only (the docs team's licence footer), MD036 off (the footer is an emphasised paragraph), MD049 underscore (GitBook's own style, ~6:1 in mariadb-docs). Check with `npx -y markdownlint-cli2@0.18.1 "**/*.md"` from `content/` → 0 findings. To prove a Markdown change keeps the display, diff the article HTML of a preview build before/after.
