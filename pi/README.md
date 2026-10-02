# Pi extensions

This directory holds the MariaDB extensions for the [Pi coding agent](https://pi.dev),
the counterpart to the top-level `claude/`, `codex/`, and `opencode/` plugin dirs.

Unlike those harnesses, Pi has no marketplace file: a pi package is any directory
with a `package.json` carrying a `pi` field (declaring its `extensions`, `skills`,
`prompts`, and/or `themes`), installed with `pi install <path | npm:… | git:…>`.
For this repo the manifest is the **repo-root [`package.json`](../package.json)**
(its `pi` field points into `pi/dev-plugin/`), so the whole repo installs as one
pi package straight from Git.

## Plugins

| Plugin | Path | Provides |
| ------ | ---- | -------- |
| `dev`  | [`dev-plugin/`](dev-plugin) | Full MariaDB skill set + the native `mariadb-shell` MCP server (registered with Pi's built-in MCP) |

## Loading them

Requires **Pi 1.0 or later**, which has MCP support built in.

```sh
pi install git:github.com/mariadb/ai-plugins   # this repo (skills + extension + MCP server)
# …or from a local checkout, at the repo root: pi install .
```

Pi discovers the skills and the extension from each package's `pi` manifest field,
and the extension registers the `mariadb` MCP server when it loads. See
[dev-plugin/README.md](dev-plugin/README.md) for the full walkthrough, including
moving off `pi-mcp-adapter`.

Skills are **vendored** into each plugin's `skills/` dir by the repo-root
[scripts/sync-skills.sh](../scripts/sync-skills.sh) — never hand-edited here.
