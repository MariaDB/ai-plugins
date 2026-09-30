# DevHub — the MariaDB AI Plugins documentation site

A static **Getting Started** site for the MariaDB AI Plugins, built by GitHub
Pages' own Jekyll. There is no build step to run and no theme gem: everything —
layouts, includes, CSS, the small progressive-enhancement JS — lives in this
folder.

## Publishing it

**Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs`.**

That is the whole setup. GitHub builds the site with its pinned `github-pages`
bundle (Jekyll 3.x) on every push to `main`.

The site is served from the custom domain in [`CNAME`](CNAME),
`ai-plugins.mariadb.org`. Only two settings in [`_config.yml`](_config.yml) are
environment-specific, and they must agree with it:

```yaml
url: "https://ai-plugins.mariadb.org"
baseurl: ""
```

Every internal link goes through `relative_url` or is relative to the page, so
moving the site is `CNAME` plus those two lines (serving from
`<org>.github.io/ai-plugins/` instead needs `baseurl: "/ai-plugins"`) and
nothing else.

## Previewing locally

[`serve.sh`](serve.sh) is the one command, and the repo-root `package.json`
exposes it as npm scripts so it also shows up in editors' script runners:

```sh
npm run docs           # serve with live reload
npm run docs:open      # …and open a browser
npm run docs:build     # build into docs/_site and exit
npm run docs:skills    # regenerate _data/skills.yml (see below)

./docs/serve.sh --port 4010        # or call it directly
./docs/serve.sh -- --incremental   # anything after -- goes straight to jekyll
./docs/serve.sh --help
```

**Mind the baseurl.** The site is served under the GitHub Pages project path, so
it lives at <http://127.0.0.1:4000/ai-plugins/> and a bare `/` answers 404. The
script prints the full URL for that reason.

### What it needs

Either of these; `serve.sh` detects which and adapts:

```sh
gem install jekyll jekyll-seo-tag jekyll-sitemap   # quick local preview
cd docs && bundle install                          # matches GitHub Pages exactly
```

The second uses the [`Gemfile`](Gemfile), which pins the `github-pages` bundle —
the same Jekyll 3.x build GitHub runs. `serve.sh` prefers it whenever a
`Gemfile.lock` is present, and otherwise runs a plain `jekyll` with
`JEKYLL_NO_BUNDLER_REQUIRE` set so it does not read the Gemfile and demand a
`github-pages` that was never installed. GitHub itself ignores the file.

**Both plugins are required, not decoration.** [`_includes/head.html`](_includes/head.html)
calls `{% seo %}`, which is an unknown Liquid tag without
`jekyll-seo-tag`, and Jekyll aborts on any plugin in `_config.yml` it cannot
require. `serve.sh` preflights them and fails with the install command rather
than producing a half-built site.

## Layout

```text
docs/
├── _config.yml               # site config; `url` + `baseurl` are the only env-specific bits
├── _data/
│   ├── nav.yml               # the header's top-row links
│   ├── subnav.yml            # the header's second-row links (external, absolute urls)
│   ├── sponsors.yml          # mariadb.org's footer sponsor banner (images hot-linked, never copied)
│   ├── paths.yml             # learning paths (each `steps` entry is a tutorial `slug`)
│   └── skills.yml            # GENERATED — see below
├── _includes/                # navbar, footer, hero wave, the two card partials
├── _layouts/                 # default → home | page | tutorial
├── _tutorials/               # the tutorial collection, one file per tutorial
├── assets/{css,js,img}/      # one stylesheet, one script, the header artwork + favicon
├── serve.sh                  # local preview (npm run docs)
├── index.html                # home
├── get-started.md            # install + MCP setup + the working example
├── tutorials.html            # filterable catalog
├── learning-paths.html
├── skills.html               # renders _data/skills.yml
├── how-it-works.md           # architecture + security model
└── mcp-tools.md              # tool reference
```

## Adding a tutorial

Drop a file in [`_tutorials/`](_tutorials). The filename becomes the URL
(`_tutorials/my-thing.md` → `/tutorials/my-thing/`), and the front matter drives
the card, the filters, the metadata header and the prev/next pager:

```yaml
---
order: 10                      # sort order; also the pager order
slug: my-thing                 # must match the filename — _data/paths.yml refers to it
title: "What the reader will do"
description: >-
  One or two sentences. Used on the card and under the page title.
level: beginner                # beginner | intermediate | advanced — drives the filter
duration: "20 min"
area: sql                      # must match a filter button in tutorials.html
tools: ["db.connect"]          # MCP tools exercised; rendered as chips
skills: ["mariadb-select"]     # skills exercised; rendered as chips
path_label: "First Steps, Step 2"   # optional footer line on the card
prerequisites:                 # optional; rendered as the "Before you start" box
  - "Markdown is allowed here."
---
```

Conventions the layout expects:

- **Each `##` heading is a numbered step** — the `step-content` counter puts a
  numbered bubble on it. Write them as actions.
- **The closing summary is `<h2 class="no-step" id="what-you-built">`**, written
  as raw HTML so it keeps its heading but loses the number.
- A tutorial with three or more headings gets a sidebar table of contents
  automatically.

Then add the `slug` to a path in [`_data/paths.yml`](_data/paths.yml) if it
belongs to one, and add its `area` to the filter buttons in
[`tutorials.html`](tutorials.html) if it introduces a new one.

## Keeping the skill catalog honest

[`_data/skills.yml`](_data/skills.yml) and the `skill_count` in
[`_config.yml`](_config.yml) are both **generated** from the plugins' own
vendored manifests, so neither the catalog nor the counts quoted in prose can
drift from what ships.

`scripts/sync-skills.sh` runs the generator itself as its last step, so a normal
sync needs nothing extra. Run it by hand after any other change to the vendored
skills — or if the sync warned that `python3` was missing:

```sh
npm run docs:skills      # or: python3 docs/regenerate-skills-data.py
```

It reads `claude/dev-plugin/skills/.skills-manifest.json` for the full list and
`claude/sql-plugin/…` for the subset marker. A new upstream layer renders with
its raw id as the title until prose for it is added to `LAYER_TEXT` in the
script — it shows up rather than vanishing.

`tool_count`, `shell_floor` and `mariadb_baseline` are still hand-maintained
`_config.yml` variables — nothing derives them — but they are each in one place
and read from Liquid, so a change is a single edit.

## Design notes

The stylesheet is a small token system in
[`assets/css/style.css`](assets/css/style.css) — `--ch-*` custom properties for
colour, spacing, radius and shadow, redefined once under
`html[data-theme="dark"]`. Nothing else in the file hardcodes a colour, so a
palette change is confined to the two token blocks at the top.

Two things worth knowing before editing:

- **The hero wave.** `--ch-wave-h` is shared by the wave SVG's height and the
  hero background's bottom overhang. They must stay equal or a band of gradient
  shows below the curve.
- **`min-width: 0` on grid children.** Grid and flex items default to
  `min-width: auto`, so a long identifier like `sandbox.list_available_versions`
  will widen the page instead of wrapping. Every grid in the file sets it, and
  `.prose code` may break mid-token — except inside a table cell, where the table
  scrolls instead.

The site was checked for horizontal overflow at 320, 360, 390, 768, 1024 and
1440 px across every page; keep it that way.

[`assets/js/site.js`](assets/js/site.js) is progressive enhancement only — theme
toggle, mobile nav, table of contents, catalog filters. Every page is fully
readable with JavaScript disabled.
