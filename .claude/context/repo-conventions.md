# Repo conventions

[← Project Context](../PROJECT_CONTEXT.md)

Two remotes: **`origin`** = `mariadb-corporation/ai-plugins` (the source of truth)
and **`fork`** = `mariadb/ai-plugins` (the tracking fork PRs arrive on, and the
install-facing org the READMEs name). **The `fork` remote had gone missing from
the local clone** once already and was re-added 2026-09-02 — check `git remote
-v` rather than trusting this file.

The `fork` remote's role is settled and is **not** a contradiction of the
source-of-truth rule: **community issues and PRs are filed on
`mariadb/ai-plugins`, then taken in by hand and landed on `origin`** (the #9 /
#7 transfers were exactly that). So the fork is the community front door, the
DevHub's GitHub/Issues links point there deliberately, and *our* PRs are still
opened on `origin`.

**The fork deliberately differs from `origin` in two files**, which every
upstream sync into the fork must preserve (MariaDB/ai-plugins PR #3, opened
2026-09-23):

- `docs/CNAME` — fork: `ai-plugins.mariadb.org`; `origin`: `ai-plugins.mariadb.com`.
- `docs/_config.yml` `url:` — fork: `https://ai-plugins.mariadb.org`.

Why: both repos serve the DevHub from GitHub Pages (`main` + `/docs`), and a
custom domain can only be claimed by one repo. With `.com` held by `origin`, the
fork's CNAME was ignored (`cname: null`) and the site fell back to
`mariadb.github.io/ai-plugins/`, where `baseurl: ""` 404s every asset. For
`.org` to be served by the fork, its DNS must point at `mariadb.github.io`; as of
2026-09-23 it still points at `websites.mariadb.org`, which 301-redirects to `.com`. The
alternative that keeps the fork 1:1 — an Actions-based Pages deploy, which
ignores `CNAME` and takes the domain from each repo's settings — was not taken.

Housekeeping rule that keeps applying: delete a merged branch by **comparing its
remote head against the `headRefOid` GitHub actually merged**, since a squash
merge leaves the branch commits unreachable from `main` and `git branch -d`
therefore refuses them (`-D` skips the very check you want). Heads kept in case
one is ever wanted back: `9262c79`, `ab05169`, `f1acb15`, `3015a48`; PR #11's
remote head was `005c15b`.

**Both fork PRs are CLOSED** on `mariadb/ai-plugins` (#1 and #2).
