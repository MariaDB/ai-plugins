# MariaDB contributor plugin for OpenCode

Version **26.9.3**

Skills for **contributing to MariaDB tooling**. Unlike the `dev`/`sql` plugins
(which vendor the MariaDB SQL/usage skills from `mariadb-docs`), this plugin
vendors the skills kept in the
[`mariadb-corporation/mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
repository under `.claude/skills/`. For now it ships **skills only** — no MCP
server.

> Note: `mariadb-shell` is currently a **private** repository. Vendoring its
> skills requires GitHub credentials (see below).

## Installation

OpenCode has no central plugin marketplace. Clone this repo (or copy this
`contributor-plugin/` directory) somewhere stable, then make its skills
discoverable — OpenCode loads skills one directory deep from `.opencode/skills/`,
`~/.config/opencode/skills/`, `.claude/skills/`, and `.agents/skills/`:

```sh
ln -s /path/to/ai-plugins/opencode/contributor-plugin/skills ~/.config/opencode/skills/mariadb-contributor
# …or per-project:
ln -s /path/to/ai-plugins/opencode/contributor-plugin/skills .opencode/skills/mariadb-contributor
```

## Skills

Skills are vendored flat under [skills/](skills/) — one directory per skill,
directly under `skills/`, as OpenCode requires. They are kept in sync by the
repo-wide updater [scripts/sync-skills.sh](../../scripts/sync-skills.sh), which
fetches `mariadb-shell`'s `.claude/skills/` tree and copies each `SKILL.md` into
`skills/<skill>/`. Because the source repo is private, the sync authenticates
with `GH_TOKEN` (or `gh auth token`); without credentials it skips this plugin.
Per-plugin provenance is recorded in [skills-source.json](skills-source.json).

## License

Plugin code is **GPL-2.0** — see [LICENSE](LICENSE). The bundled skills are
vendored from several source repositories and retain their original licenses;
see [additional-skills/README.md](../../additional-skills/README.md) for the full list of sources and their
licensing.
