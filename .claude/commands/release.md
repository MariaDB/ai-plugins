---
description: Cut an ai-plugins release, suggesting its next YY.MM.x version and raising the mariadb-shell floor to the latest shell release where there is a newer one, PR it, then sync the fork. Usage: /release [version|-] [shell-version|-]
---

# Release Command

Arguments as typed: `$ARGUMENTS`

Split that string on whitespace. The first word is the plugin version, the
second is the new mariadb-shell floor. Both are optional, so a bare `/release`
works. A `-` in a position means "not given", so the floor can be given without
the version (`/release - 26.10.3`). What is not given is suggested in step 2:

- the plugin version: the next `YY.MM.x` version (see step 2);
- the floor: the latest published mariadb-shell release, when it is newer than
  the current floor. Otherwise it stays where it is.

From here on, "the plugin version" and "the floor" mean the two versions this
release ships, given or suggested; `<version>` and `<floor>` stand for them in
the commands below. If a third word is present, stop and ask what it means.

Both versions must be a bare `MAJOR.MINOR.PATCH` such as `26.10.0` — no `v` prefix. The
version *inside* this repo (manifests, CHANGELOG headings) is bare; only the git
tag carries the `v` (`v26.10.0`). Strip a leading `v` if one was given and say so.

**The two versions are independent.** The plugin version is the ai-plugins version: the plugin
manifests, the CHANGELOG headings and the tag. The floor is the `MARIADB_SHELL_VERSION`
floor, the oldest mariadb-shell the launchers accept. Through 26.9.5 the two were
always equal; that is no longer required. With no floor given it stays where it is
and the release ships on top of the current shell version — unless a newer shell
release exists, in which case step 2 suggests raising the floor to it.

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
- `v<version>` must not already exist as a tag locally or on either remote
  (`git ls-remote --tags <remote>`, once per remote — `ls-remote` takes one
  remote and would read `fork` as a pattern). If it does, stop. When the
  version is suggested, check this in step 2, once it is known.

## 2. Check the versions

Do all of this before changing anything, and report what you find in one
summary: the plugin version and the floor, each with its current value, the
value this release ships, and whether that was given or suggested.

**When anything was suggested, stop and ask the user to confirm the summary.**
They may accept it, or change either version, for example to keep the current
floor although a newer shell exists. Run the checks below again for what they
changed. When both were given, report the summary and go on.

**The plugin version.** List this repo's tags (`git tag -l 'v*' | sort -V`) and
take the highest. Report it as the previous version.

- **None given:** suggest `YY.MM.x` from today's date (`date +%y.%-m`): `YY` is
  the year's last two digits, `MM` the month without a leading zero (`26.9.0`,
  never `26.09.0`: semver forbids leading zeros), and `x` counts the releases
  of that month. It is `0` for the month's first release, and one more than the
  highest `x` among the tags that start with `vYY.MM.` otherwise. If the
  suggestion does not sort above the highest tag (one from a later month
  exists), stop and report it. Check that `v<suggestion>` is not a tag, locally
  or on either remote.
- **One given:** it must sort above the highest tag, or stop. If it does not
  follow `YY.MM.x` for this month, say so and ask whether to use it anyway.

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

- **The current floor itself is not in the list** (it was raised on `main`
  ahead of the shell release) → stop, whatever was given. A release must not
  ship a floor no launcher can install. Say whether the floor's release is
  still to come or whether the floor should go back to a published one, and
  let the user decide. A floor given here that *is* published resolves it.
- **No floor given:** check whether the current floor is still the latest
  published shell release (the highest `tagName`). If it is, the floor stays
  unchanged. If a newer one exists, suggest raising the floor to it, naming
  both versions and the latest one's publish date, and continue with it as if
  it had been given (the checks below then pass trivially). The confirmation
  of the summary settles it.
- **A floor given:**
  - `v<floor>` is not in the list → stop. The shell floor must never sit above a
    published release, or every launcher would demand a binary that does not
    exist.
  - It is below the current floor → stop and ask; lowering the floor is not a
    normal release step.
  - It equals the current floor → nothing to move; continue as if no floor was given.
  - A version higher than it exists → say so and ask whether to use the given floor anyway.
  - Otherwise continue, and report the publish date of `v<floor>`.

## 3. Branch and set the versions

```bash
git switch -c wip/<version>
scripts/set-mariadb-shell-version.sh <floor>   # only when the floor moves (step 2)
scripts/set-plugin-version.sh <version>
```

Run them in that order and stop at the first non-zero exit. Skip the shell-floor
script entirely when the floor is not moving. After each, note how many files
changed (`git status --short | wc -l`). For reference, 26.9.5 moved 33 files for
the shell floor and 17 for the plugin version; the Hermes plugins, added after
26.10.2, add 8 and 6 to those, and `hermes/guard-plugin` (26.10.4) 2 more to the
plugin version — 26.10.4 moved 39 and 25; a very different count is worth
looking into before going on. If a version was already at its target the script
changes nothing — say so, don't treat it as a failure. Commit each step on its
own so the PR is reviewable per step.

## 4. Re-vendor the skills

```bash
scripts/sync-skills.sh
```

No argument: it vendors the latest upstream `main`. Afterwards, **look at
`git status` rather than assuming the sync shipped something** — often only the
thirteen `skills-source.json` provenance files move (`hermes/guard-plugin` vendors
no skills, so it has none). Record, for the release notes:
the old → new upstream commits for `mariadb-docs` and `mariadb-shell` (from the
`skills-source.json` diffs), any skills added, removed or changed, and the skill
counts per variant (82 dev / 47 sql / 2 contributor as of 26.9.3). Commit.

## 5. CHANGELOG entries

Add a `## [<version>] - <today>` section to the top of all fourteen `*/*/CHANGELOG.md`
files, following the wording and structure of the previous release's section in
each file. Write only what actually changed in *that* plugin: the contributor
plugins have no MCP server, so no shell-floor line; the sql plugins have their
own skill count; `hermes/guard-plugin` has neither skills nor an MCP server, so
when nothing in it changed its section is the version bump alone. Mention the shell floor only when it moved in this release (then
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
git push -u origin wip/<version>
gh pr create --repo mariadb-corporation/ai-plugins --base main --head wip/<version> --title "Release <version>: …" --body-file <file>
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

Create an annotated tag `v<version>` on the squash commit. The annotation's body is the
release notes: a short prose summary in the style of the v26.9.3 release (read it
with `gh release view v26.9.3 --repo mariadb-corporation/ai-plugins`). It states
the mariadb-shell floor the release requires and whether it moved, and ends with
"See each plugin's CHANGELOG.md [<version>] section for details."

Push the **same tag object** to both remotes (`git push origin v<version>` and
`git push fork v<version>`) and verify with `git ls-remote --tags <remote> v<version>`, once per remote, that both
point at the same object.

Publish a **prerelease** on both repos. `gh` refuses `--notes-from-tag` together
with `--repo`, so extract the body to a file first:

```bash
git tag -l --format='%(contents:body)' v<version> > <scratch>/notes.md
gh release create v<version> --repo <repo> --title v<version> --notes-file <scratch>/notes.md --prerelease --verify-tag
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
git switch -c sync/fork-<version> fork/main
git merge origin/main -m "Sync with mariadb-corporation/ai-plugins main (#<PR>)"
```

(add the commit attribution line to the message if a merge commit is made.) A
conflict means someone committed to the fork directly — stop and show it.

Before pushing, verify:

- `git diff origin/main HEAD` is empty.

If it is not, stop and show it. Otherwise push with
`git push fork HEAD:main` (a fast-forward of the fork's `main`; it will be
refused if the fork moved meanwhile — then fetch and merge again, don't force).
Return to `main` and delete the local `wip/<version>` and `sync/fork-<version>` branches, and
delete `wip/<version>` on `origin` once its remote head matches the PR's `headRefOid`.

## 11. Report

Tell the user the release is published, with:

- the merged PR and its squash commit
- the tag `v<version>` and its tag object
- both release URLs
- that the fork is synced and its tree matches `origin/main`
- anything that did not go as expected

Then record the finished release with `/checkpoint .` and open a small PR for it,
as was done after 26.9.3 (#21).
