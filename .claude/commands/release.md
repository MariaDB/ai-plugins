---
description: Cut an ai-plugins release that matches a published mariadb-shell version, PR it, then sync the fork. Usage: /release <version>
---

# Release Command

Version to release: $1

If $1 is empty, ask for the version before doing anything else. It must be a
bare `MAJOR.MINOR.PATCH` such as `26.9.4` — no `v` prefix. The version *inside*
this repo (manifests, CHANGELOG headings) is bare; only the git tag carries the
`v` (`v26.9.4`). Strip a leading `v` if one was given and say so.

Read `.claude/PROJECT_CONTEXT.md`, then `.claude/context/release-history.md` and
`.claude/context/repo-conventions.md` before starting: the previous release's
notes are the model for this one.

Remotes: `origin` = `mariadb-corporation/ai-plugins` (source of truth, where the
PR goes) and `fork` = `mariadb/ai-plugins`. Check `git remote -v` — the `fork`
remote has gone missing before. If either is missing, stop and report it.

## 1. Preconditions

- `git status --short` must be clean and the current branch must be `main`,
  level with `origin/main` after `git fetch origin fork --tags`. If not, stop
  and report rather than stashing or resetting anything.
- `v$1` must not already exist as a tag locally or on either remote
  (`git ls-remote --tags origin fork`). If it does, stop.

## 2. Check $1 is the latest mariadb-shell release

Every mariadb-shell release is a **prerelease**, so `releases/latest` 404s —
do not use it. List the releases instead:

```
gh release list --repo mariadb-corporation/mariadb-shell --exclude-drafts --limit 30 --json tagName,isPrerelease,publishedAt
```

Sort the `tagName`s as versions (strip the `v`; `sort -V`), not by date. Then:

- `v$1` is not in the list → stop. The shell floor must never sit above the
  newest published release, or every launcher would demand a binary that does
  not exist.
- `v$1` exists but a higher version does too → stop and ask whether to release
  $1 anyway or use the newer version.
- `v$1` is the highest → continue, and report its publish date.

## 3. Branch and set the versions

```
git switch -c wip/$1
scripts/set-mariadb-shell-version.sh $1
scripts/set-plugin-version.sh $1
```

Run them in that order and stop at the first non-zero exit. After each, note how
many files changed (`git status --short | wc -l`). For reference, 26.9.3 moved 31
files for the shell floor and 17 for the plugin version; a very different count
is worth looking into before going on. If a version was already at $1 the script
changes nothing — say so, don't treat it as a failure. Commit each step on its
own so the PR is reviewable per step.

## 4. Re-vendor the skills

```
scripts/sync-skills.sh
```

No argument: it vendors the latest upstream `main`. Afterwards, **look at
`git status` rather than assuming the sync shipped something** — often only the
ten `skills-source.json` provenance files move. Record, for the release notes:
the old → new upstream commits for `mariadb-docs` and `mariadb-shell` (from the
`skills-source.json` diffs), any skills added, removed or changed, and the skill
counts per variant (82 dev / 47 sql / 2 contributor as of 26.9.3). Commit.

## 5. CHANGELOG entries

Add a `## [$1] - <today>` section to the top of all ten `*/*/CHANGELOG.md`
files, following the wording and structure of the previous release's section in
each file. Write only what actually changed in *that* plugin: the contributor
plugins have no MCP server, so no shell-floor line; the sql plugins have their
own skill count. Commit.

## 6. Verify

Run `./run_tests.py -m static` and report the result. If it fails, stop and show
the failure — do not open the PR on a red run.

## 7. Checkpoint

Run the `/checkpoint` command with `.` as the target, recording the release as
in progress (PR about to open) in `release-history.md`, `current-state.md` and
the index's "Latest work streams" and "Git state". Commit it on this branch so it
ships in the release PR.

## 8. Open the PR

```
git push -u origin wip/$1
gh pr create --repo mariadb-corporation/ai-plugins --base main --head wip/$1 --title "Release $1: …" --body-file <file>
```

Title in the style of #20 (`Release 26.9.3: shell floor, plugin version, and a
skills re-vendor`), naming what this release actually contains. The body lists
each step with its file counts and the skill-sync findings, and ends with the
PR attribution line.

Then **stop and ask the user to review and merge the PR**, giving its URL. Do not
merge it yourself. Wait until the user says it is merged, then confirm with
`gh pr view <N> --repo mariadb-corporation/ai-plugins --json state,mergeCommit,headRefOid`
that `state` is `MERGED`, and note the squash commit.

## 9. Tag and publish the release

```
git switch main && git pull --ff-only origin main
```

Create an annotated tag `v$1` on the squash commit. The annotation's body is the
release notes: a short prose summary in the style of the v26.9.3 release (read it
with `gh release view v26.9.3 --repo mariadb-corporation/ai-plugins`), ending with
"See each plugin's CHANGELOG.md [$1] section for details."

Push the **same tag object** to both remotes (`git push origin v$1` and
`git push fork v$1`) and verify with `git ls-remote --tags origin fork` that both
point at the same object.

Publish a **prerelease** on both repos. `gh` refuses `--notes-from-tag` together
with `--repo`, so extract the body to a file first:

```
git tag -l --format='%(contents:body)' v$1 > <scratch>/notes.md
gh release create v$1 --repo <repo> --title v$1 --notes-file <scratch>/notes.md --prerelease --verify-tag
```

for `<repo>` = `mariadb-corporation/ai-plugins` and `mariadb/ai-plugins`.

## 10. Sync the fork — keeping its docs/CNAME

The fork deliberately differs from `origin` in two files, and the sync must keep
both:

- `docs/CNAME` — fork: `ai-plugins.mariadb.org` (origin: `ai-plugins.mariadb.com`)
- `docs/_config.yml` `url:` — fork: `https://ai-plugins.mariadb.org`

Sync with a **merge** of `origin/main` into `fork/main`, never a reset or force
push — the fork-only commits must survive:

```
git fetch fork
git switch -c sync/fork-$1 fork/main
git merge --no-ff origin/main -m "Sync with mariadb-corporation/ai-plugins main (#<PR>)" -m "Keeps the fork-only docs/CNAME (ai-plugins.mariadb.org) and _config.yml url:."
```

(add the commit attribution line to the message.) If `docs/CNAME` or
`docs/_config.yml` conflicts, resolve it by keeping the fork's domain values and
taking everything else from `origin` — `_config.yml`'s `shell_floor` must end up
at $1.

Before pushing, verify:

- `cat docs/CNAME` prints `ai-plugins.mariadb.org`.
- `git diff origin/main HEAD --stat` shows **only** `docs/CNAME` and
  `docs/_config.yml`, and the `_config.yml` diff is only the `url:` lines.

If either check fails, stop and show it. Otherwise push with
`git push fork HEAD:main` (a fast-forward of the fork's `main`; it will be
refused if the fork moved meanwhile — then fetch and merge again, don't force).
Return to `main` and delete the local `wip/$1` and `sync/fork-$1` branches, and
delete `wip/$1` on `origin` once its remote head matches the PR's `headRefOid`.

## 11. Report

Tell the user the release is published, with:

- the merged PR and its squash commit
- the tag `v$1` and its tag object
- both release URLs
- that the fork is synced, with `docs/CNAME` still `ai-plugins.mariadb.org`
- anything that did not go as expected

Then record the finished release with `/checkpoint .` and open a small PR for it,
as was done after 26.9.3 (#21).
