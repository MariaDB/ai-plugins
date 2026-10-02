---
description: Cut an ai-plugins release, optionally raising the mariadb-shell floor, PR it, then sync the fork. Usage: /release <version> [shell-version]
---

# Release Command

Version to release: $1
New mariadb-shell floor (optional): $2

If $1 is empty, ask for the version before doing anything else. Both versions
must be a bare `MAJOR.MINOR.PATCH` such as `26.10.0` — no `v` prefix. The
version *inside* this repo (manifests, CHANGELOG headings) is bare; only the git
tag carries the `v` (`v26.10.0`). Strip a leading `v` if one was given and say so.

**The two versions are independent.** $1 is the ai-plugins version: the plugin
manifests, the CHANGELOG headings and the tag. $2 is the `MARIADB_SHELL_VERSION`
floor, the oldest mariadb-shell the launchers accept. Through 26.9.5 the two were
always equal; that is no longer required. With no $2 the floor stays where it is
and the release ships on top of the current shell version.

Read `.claude/PROJECT_CONTEXT.md`, then `.claude/context/release-history.md` and
`.claude/context/repo-conventions.md` before starting: the previous release's
notes are the model for this one.

Remotes: `origin` = `mariadb-corporation/ai-plugins` (source of truth, where the
PR goes) and `fork` = `mariadb/ai-plugins`. Check `git remote -v` — the `fork`
remote has gone missing before. If either is missing, stop and report it.

## 1. Preconditions

- `git status --short` must be clean and the current branch must be `main`,
  level with `origin/main` after `git fetch --multiple --tags origin fork`. If not, stop
  and report rather than stashing or resetting anything.
- `v$1` must not already exist as a tag locally or on either remote
  (`git ls-remote --tags <remote>`, once per remote — `ls-remote` takes one
  remote and would read `fork` as a pattern). If it does, stop.

## 2. Check the versions

**The plugin version.** List this repo's tags (`git tag -l 'v*' | sort -V`) and
take the highest. $1 must sort above it, or stop. Report the previous version.

**The current shell floor** is `shell_floor` in `docs/_config.yml`; it also
appears as the launchers' fallback (`VERSION="${MARIADB_SHELL_VERSION:-<v>}"`).
Read it and report it.

**The published mariadb-shell releases.** Every mariadb-shell release is a
**prerelease**, so `releases/latest` 404s — do not use it. List the releases
instead:

```bash
gh release list --repo mariadb-corporation/mariadb-shell --exclude-drafts --limit 30 --json tagName,isPrerelease,publishedAt
```

Sort the `tagName`s as versions (strip the `v`; `sort -V`), not by date.

- **No $2:** the floor stays. If a shell release newer than the floor exists,
  mention it (with its publish date) so the user can choose to raise the floor,
  but do not stop.
- **$2 given:**
  - `v$2` is not in the list → stop. The shell floor must never sit above a
    published release, or every launcher would demand a binary that does not
    exist.
  - $2 is below the current floor → stop and ask; lowering the floor is not a
    normal release step.
  - $2 equals the current floor → nothing to move; continue as if no $2 was given.
  - A version higher than $2 exists → say so and ask whether to use $2 anyway.
  - Otherwise continue, and report the publish date of `v$2`.

## 3. Branch and set the versions

```bash
git switch -c wip/$1
scripts/set-mariadb-shell-version.sh $2   # only when the floor moves (step 2)
scripts/set-plugin-version.sh $1
```

Run them in that order and stop at the first non-zero exit. Skip the shell-floor
script entirely when the floor is not moving. After each, note how many files
changed (`git status --short | wc -l`). For reference, 26.9.5 moved 33 files for
the shell floor and 17 for the plugin version; a very different count is worth
looking into before going on. If a version was already at its target the script
changes nothing — say so, don't treat it as a failure. Commit each step on its
own so the PR is reviewable per step.

## 4. Re-vendor the skills

```bash
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
own skill count. Mention the shell floor only when it moved in this release (then
name the new floor), and carry each plugin's `[Unreleased]` section, if it has
one, into the new section. Commit.

## 6. Verify

Run `./run_tests.py -m static` and report the result. If it fails, stop and show
the failure — do not open the PR on a red run.

## 7. Checkpoint

Run the `/checkpoint` command with `.` as the target, recording the release as
in progress (PR about to open) in `release-history.md`, `current-state.md` and
the index's "Latest work streams" and "Git state". Commit it on this branch so it
ships in the release PR.

## 8. Open the PR

```bash
git push -u origin wip/$1
gh pr create --repo mariadb-corporation/ai-plugins --base main --head wip/$1 --title "Release $1: …" --body-file <file>
```

Title in the style of #20 (`Release 26.9.3: shell floor, plugin version, and a
skills re-vendor`), naming what this release actually contains — leave out
"shell floor" when it didn't move. The body lists
each step with its file counts and the skill-sync findings, and ends with the
PR attribution line.

Then **stop and ask the user to review and merge the PR**, giving its URL. Do not
merge it yourself. Wait until the user says it is merged, then confirm with
`gh pr view <N> --repo mariadb-corporation/ai-plugins --json state,mergeCommit,headRefOid`
that `state` is `MERGED`, and note the squash commit.

## 9. Tag and publish the release

```bash
git switch main && git pull --ff-only origin main
```

Create an annotated tag `v$1` on the squash commit. The annotation's body is the
release notes: a short prose summary in the style of the v26.9.3 release (read it
with `gh release view v26.9.3 --repo mariadb-corporation/ai-plugins`). It states
the mariadb-shell floor the release requires and whether it moved, and ends with
"See each plugin's CHANGELOG.md [$1] section for details."

Push the **same tag object** to both remotes (`git push origin v$1` and
`git push fork v$1`) and verify with `git ls-remote --tags <remote> v$1`, once per remote, that both
point at the same object.

Publish a **prerelease** on both repos. `gh` refuses `--notes-from-tag` together
with `--repo`, so extract the body to a file first:

```bash
git tag -l --format='%(contents:body)' v$1 > <scratch>/notes.md
gh release create v$1 --repo <repo> --title v$1 --notes-file <scratch>/notes.md --prerelease --verify-tag
```

for `<repo>` = `mariadb-corporation/ai-plugins` and `mariadb/ai-plugins`.

## 10. Sync the fork

The fork's `main` carries the same tree as `origin/main`, `docs/CNAME`
(`ai-plugins.mariadb.org`) included — the fork's Pages is what serves it. Sync with a **merge** of
`origin/main` into `fork/main`, never a reset or force push (a fast-forward when
the fork has no commits of its own). Since 26.9.5 the fork's `main` *is*
`origin/main` (same commit), so this is expected to be a plain fast-forward:

```bash
git fetch fork
git switch -c sync/fork-$1 fork/main
git merge origin/main -m "Sync with mariadb-corporation/ai-plugins main (#<PR>)"
```

(add the commit attribution line to the message if a merge commit is made.) A
conflict means someone committed to the fork directly — stop and show it.

Before pushing, verify:

- `git diff origin/main HEAD` is empty.

If it is not, stop and show it. Otherwise push with
`git push fork HEAD:main` (a fast-forward of the fork's `main`; it will be
refused if the fork moved meanwhile — then fetch and merge again, don't force).
Return to `main` and delete the local `wip/$1` and `sync/fork-$1` branches, and
delete `wip/$1` on `origin` once its remote head matches the PR's `headRefOid`.

## 11. Report

Tell the user the release is published, with:

- the merged PR and its squash commit
- the tag `v$1` and its tag object
- both release URLs
- that the fork is synced and its tree matches `origin/main`
- anything that did not go as expected

Then record the finished release with `/checkpoint .` and open a small PR for it,
as was done after 26.9.3 (#21).
