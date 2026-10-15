# MariaDB contributor plugin for Hermes Agent

Version **26.10.2**

Skills for **contributing to MariaDB tooling**, for
[Hermes Agent](https://hermes-agent.nousresearch.com/). Unlike the `mariadb-dev`
and `mariadb-sql` plugins (which vendor the MariaDB SQL/usage skills from
`mariadb-docs`), this plugin vendors the skills kept in the
[`mariadb-corporation/mariadb-shell`](https://github.com/mariadb-corporation/mariadb-shell)
repository under `.claude/skills/`. For now it ships **skills only** — no MCP
server.

It is a portable **Agent Plugins v1** package: a root [plugin.json](plugin.json)
and a [skills/](skills/) directory.

## Installation

```sh
hermes plugins install mariadb/ai-plugins#hermes/contributor-plugin --enable
```

`--enable` is needed because Hermes installs portable packages **disabled**.
Without it, run `hermes plugins enable mariadb-contributor` afterwards.

To update later, run `hermes plugins update mariadb-contributor`; to remove it,
`hermes plugins remove mariadb-contributor`.

## Skills

Hermes lists plugin skills through its `skills_list` and `skill_view` tools under
a namespace it derives from the plugin, such as
`agent-plugin-mariadb-contributor-<hash>:create-shell-plugin`. They are read-only.

Skills are vendored flat under [skills/](skills/). They are kept in sync by the
repo-wide updater [scripts/sync-skills.sh](../../scripts/sync-skills.sh), which
fetches `mariadb-shell`'s `.claude/skills/` tree and copies each `SKILL.md` into
`skills/<skill>/`. The repository is public, so no credentials are needed; a
`GH_TOKEN` (or `gh auth token`) is used when available, for the higher API rate
limit. Per-plugin provenance is recorded in [skills-source.json](skills-source.json).

## License

Plugin code is **GPL-2.0** — see [LICENSE](LICENSE). The bundled skills are
vendored from several source repositories and retain their original licenses;
see [additional-skills/README.md](../../additional-skills/README.md) for the full list of sources and their
licensing.
