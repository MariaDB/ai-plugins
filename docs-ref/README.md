# Reference docs (GitBook source + offline preview)

`docs-ref/` holds the **reference documentation** for the MariaDB AI Plugins,
written for the MariaDB documentation at <https://mariadb.com/docs/>. That site
is GitBook, which cannot build offline, so this folder also carries a small
[Docusaurus](https://docusaurus.io/) site that renders the same files in the
mariadb.com/docs theme.

The DevHub in [`../docs/`](../docs/) is a different thing: tutorials and a
getting-started site. This folder is the reference.

| Path | What it is |
| --- | --- |
| `content/` | **The GitBook source.** Markdown plus GitBook blocks, laid out as a GitBook space. This is what gets ported. |
| `content/SUMMARY.md` | GitBook's navigation. The preview's sidebar is generated from it, so it is the only place the page tree is defined. |
| `content/README.md` | A stand-in for the Enterprise Tools space landing page. Only its `## MariaDB AI Plugins` section is meant for porting. |
| `content/mariadb-ai-plugins/` | The product docs. |
| `content/.gitbook/assets/` | Images, as GitBook stores them. Reference them as `.gitbook/assets/<file>` (with the right `../` depth). |
| `docusaurus.config.js`, `sidebars.js`, `src/`, `static/` | The preview site only. Never ported. |
| `scripts/generate-skill-pages.py` | Generates the Skills Reference pages. |

## Preview

```sh
cd docs-ref
npm ci            # once
npm start         # live reload  → http://localhost:3000/docs/tools/mariadb-ai-plugins
npm run build     # static build → build/, then: npm run serve
```

From the repository root: `npm run docs-ref`, `npm run docs-ref:build`,
`npm run docs-ref:serve`.

The build fails on a broken link or a missing `content-ref` target, so a clean
build is a useful check before porting.

## Publishing the preview on a web server

`npm run build` writes a self-contained static site to `build/`. Every page is
a directory with an `index.html`, so no rewrite rules are needed.

The site is built for the path **`/docs/`**, like mariadb.com/docs. To serve it
from somewhere else, set the path at build time; it must match where the
files end up:

```sh
DOCS_BASE_URL=/ai-plugins-docs/ npm run build
```

### Apache httpd

Copy the **contents** of `build/` into the directory served at that path, for
example `DocumentRoot/docs/`. Include `.htaccess`, which the build generates
with the matching `ErrorDocument 404` line:

```sh
rsync -a --delete build/ user@host:/var/www/html/docs/
```

Apache's defaults do the rest: `mod_dir` serves `index.html` and redirects
`/docs/tools/mariadb-ai-plugins` to the trailing-slash URL. For `.htaccess` to
take effect, the directory needs `AllowOverride FileInfo` (or `All`). Without
it, everything still works except that unknown URLs get Apache's own 404 page.

## Writing pages

Follow the MariaDB documentation conventions, since the pages go there
unchanged. The canonical guides live in the `mariadb-docs` repository:
`dev-docs/gitbook-syntax.md` and `dev-docs/style-guide.md`. The short version:

- Every page starts with frontmatter carrying a `description:`. GitBook shows it
  under the title, and so does the preview.
- One `#` title per page, sections from `##`, headings in Title Case.
- Use GitBook blocks — `{% hint %}`, `{% tabs %}`, `{% code %}`,
  `{% content-ref %}`, `{% columns %}` — not plain-Markdown lookalikes. Hint
  styles are `info`, `warning`, `danger` and `success` only.
- Links within the space are relative `.md` links. Add every new page to
  `content/SUMMARY.md`, or it is not in the navigation.
- American English, second person, present tense, no "simply"/"currently".

### Generated pages

The pages under `content/mariadb-ai-plugins/skills-reference/` — all but its
`README.md` — are **generated** from the skills the plugins ship. Don't edit
them by hand; after `scripts/sync-skills.sh`, run:

```sh
python3 docs-ref/scripts/generate-skill-pages.py     # or: npm run docs-ref:skills
```

## How the preview renders GitBook blocks

[`docusaurus-plugin-gitbook`](https://github.com/jasny/docusaurus-plugin-gitbook)
does most of the work. [`src/remark/gitbook-extras.js`](src/remark/gitbook-extras.js)
fills three gaps, without patching the package:

- **`{% content-ref %}`** has no transformer in the plugin, and its tokenizer
  does not accept a hyphen in a block name. A pre-pass renames the block, and a
  transformer renders it as a link card titled after the target page.
- **Blocks nested in other blocks** (a `content-ref` inside a `column`) are
  dropped by the plugin's own transformers; each block is given its full inner
  source instead.
- **The `description`** is rendered as the lead paragraph, and **directory
  links** (`[x](dir/)`) are resolved to the directory's `README.md`.

[`src/theme/Navbar`](src/theme/Navbar/index.js) adds the space-tab row of the
mariadb.com/docs header, and [`src/css/mariadb-gitbook.css`](src/css/mariadb-gitbook.css)
carries the theme, with the colour scales copied from the live site in both
light and dark mode.

Not rendered: `{% include %}` (shown as a placeholder by the plugin), Font
Awesome page icons in the sidebar, and GitBook's search.

## Porting to mariadb-docs

The target is the **Enterprise Tools** space (`tools/` in
`mariadb-corporation/mariadb-docs`, published at
`https://mariadb.com/docs/tools/`), next to MariaDB Enterprise MCP Server and
MariaDB AI RAG. The preview uses the same URL layout.

1. Copy `content/mariadb-ai-plugins/` to `tools/mariadb-ai-plugins/`, and any
   images from `content/.gitbook/assets/` to `tools/.gitbook/assets/`.
2. Add the `* [MariaDB AI Plugins](mariadb-ai-plugins/README.md)` subtree from
   `content/SUMMARY.md` to `tools/SUMMARY.md`.
3. Add the `## MariaDB AI Plugins` section of `content/README.md` to
   `tools/README.md`.
4. Rewrite links to other spaces as link aliases, e.g.
   `https://mariadb.com/docs/server/security/cve` → `{server}/security/cve`
   (see `dev-docs/link-aliases.md` there). The preview keeps absolute URLs
   because it cannot resolve aliases.
5. Run `docs-check` in mariadb-docs before opening the PR.
