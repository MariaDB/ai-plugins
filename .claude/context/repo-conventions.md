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

**The fork and `origin` carry identical trees again** (`wip/docs-uri-cleanup`,
2026-09-28). `ai-plugins.mariadb.com` is being dropped and
`ai-plugins.mariadb.org` is the only DevHub host, so `origin`'s `docs/CNAME` and
`docs/_config.yml` `url:` now hold the `.org` values the fork alone used to
carry (fork PR #3, `6682ff1`). A fork sync is a plain merge whose result must
diff empty against `origin/main`.

History, in case it comes back: both repos serve the DevHub from GitHub Pages
(`main` + `/docs`), and a custom domain can only be claimed by one repo. While
`origin` held `.com`, the fork had to carry its own CNAME, or it was ignored
(`cname: null`) and the site fell back to `mariadb.github.io/ai-plugins/`, where
`baseurl: ""` 404s every asset. **Only the fork's Pages can serve `.org`** (DNS
points at `mariadb.github.io`), so `origin`'s Pages has to give up the domain,
either disabled or with its custom domain cleared.

**`https://ai-plugins.mariadb.org/` is LIVE** (verified 2026-09-23), served by
the fork's Pages: DNS is a CNAME to `mariadb.github.io` (it used to point at
`websites.mariadb.org`, which 301-redirected to `.com`), the fork's Pages
`cname` is `ai-plugins.mariadb.org` with an approved certificate, the canonical
tag names `.org`, and `mariadb.github.io/ai-plugins/` 301s to it. **"Enforce
HTTPS" is still off on both repos' Pages settings**, so that 301 lands on
`http://` and plain-http visits aren't upgraded.

Housekeeping rule that keeps applying: delete a merged branch by **comparing its
remote head against the `headRefOid` GitHub actually merged**, since a squash
merge leaves the branch commits unreachable from `main` and `git branch -d`
therefore refuses them (`-D` skips the very check you want). Heads kept in case
one is ever wanted back: `9262c79`, `ab05169`, `f1acb15`, `3015a48`; PR #11's
remote head was `005c15b`.

**The fork's canonical name is `MariaDB/ai-plugins`** — the org login has been
`MariaDB` since 2013, and the repo was never renamed or transferred. The `fork`
remote was re-added in lowercase (`mariadb/`), and GitHub prints "This
repository moved" on every **push** to a URL whose case differs from the
canonical one; fetches and clones print nothing, and the web UI serves both
spellings. Fixed locally 2026-09-24 with `git remote set-url fork
git@github.com:MariaDB/ai-plugins.git` — if the remote is ever re-added, use
that casing. The ~20 lowercase `mariadb/ai-plugins` references in READMEs and
manifests are left alone: users only fetch, so the notice never reaches them.

**Fork PRs**: #1 and #2 are CLOSED (transferred as #9 / #7); #3 was our own `.org` domain change, merged on the fork. **#4** (`Add Laravel skills for MariaDB`, @Rhaima96, still OPEN on the fork) was transferred on 2026-09-25 as **origin PR #28** — close it with a link back once #28 merges.

**How a fork PR is transferred** (the #28 recipe): `git fetch fork pull/<N>/head:fork-pr-<N>`, branch from `origin/main`, then **cherry-pick only the contributor's commits** (`git log main..fork-pr-<N>` also lists the fork's sync commits, which must stay out). Cherry-pick keeps the original author and author date and makes you the committer. Fixes of ours go on top as separate commits, never amended into theirs. The PR body opens with a credit line (`Transferred from MariaDB/ai-plugins#<N> by @<login>`) followed by their original description.
