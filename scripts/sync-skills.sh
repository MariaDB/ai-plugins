#!/usr/bin/env bash
#
# Copyright (c) 2026, MariaDB plc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, version 2.0,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License, version 2.0, for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# sync-skills.sh — vendor MariaDB agent skills into every plugin in this repo.
#
# Downloads the agent-skills/ tree from mariadb-corporation/mariadb-docs at a
# given ref ONCE, reads its .skills-manifest.json, and copies every skill
# directory into each plugin's skills/ dir. It also vendors this repo's own
# additional-skills/ tree. Re-running is idempotent. Per-plugin provenance is
# written to skills-source.json.
#
# All plugins use a FLAT skill layout: every skill dir is placed directly under
# skills/<skill>/, regardless of how it is grouped upstream. This is what
# OpenCode requires (it discovers skills only one directory deep), and it keeps
# every plugin identical on disk. The vendored .skills-manifest.json is rewritten
# so each skill `path` points at its flat location, keeping the test suites'
# manifest-driven loaders valid. The manifest's layer grouping is preserved
# (only the paths flatten), so tests that key off a skill's layer still work.
#
# Local additional-skills/ (this repo's own skills, not from upstream) are copied
# flat alongside the upstream skills and recorded in the manifest under an
# "additional" layer so the disk<->manifest consistency tests pass.
#
# Plugins kept in sync (relative to repo root), all flat:
#   - claude/dev-plugin     (Claude Code)   — all skill layers
#   - codex/dev-plugin      (Codex)         — all skill layers
#   - opencode/dev-plugin   (OpenCode)      — all skill layers
#   - pi/dev-plugin         (Pi / pi.dev)   — all skill layers
#   - claude/sql-plugin     (Claude Code)   — statements + functions + topical only
#   - codex/sql-plugin      (Codex)         — statements + functions + topical only
#   - opencode/sql-plugin   (OpenCode)      — statements + functions + topical only
#   - claude/contributor-plugin   (Claude Code)  — mariadb-shell .claude/skills only
#   - codex/contributor-plugin    (Codex)        — mariadb-shell .claude/skills only
#   - opencode/contributor-plugin (OpenCode)     — mariadb-shell .claude/skills only
#
# The contributor-* plugins vendor a DIFFERENT source repo — the skills tracked in
# mariadb-corporation/mariadb-shell under .claude/skills/ (public; no token needed).
# They share none of the mariadb-docs layers or the local additional-skills/.
#
# The dev-* plugins vendor EVERY upstream layer — granular/statements,
# granular/functions, granular/tools (client tools), granular/connectors
# (database connector skills), topical — plus the local additional-skills/.
#
# The sql-* plugins are a SQL-focused variant vendored from an explicit
# include-list: the upstream layers granular/statements, granular/functions and
# topical, plus the local additional-skills/sql subfolder. So the client-tool and
# connector layers, and the additional-skills/rest, schema-management and
# migrator subfolders, are dev-only.
# vendor_into() takes an optional list of include keys; upstream layers are picked
# by their manifest layer key, and local additional-skills/ subfolders by an
# "additional-<subfolder>" key (or "additional" for every subfolder). Only the
# selected upstream layers are written into the vendored .skills-manifest.json,
# and only the selected additional-skills/ subfolders are copied. With NO include
# list, every upstream layer plus every additional-skills/ subfolder is vendored
# — the full dev behavior.
#
# Usage:
#   scripts/sync-skills.sh [REF]
#
# REF defaults to the latest commit on the upstream default branch (main); pass a
# tag/branch/commit to sync a specific version. The resolved commit SHA that was
# synced is always recorded in each plugin's skills-source.json.

set -euo pipefail

SOURCE_REPO="mariadb-corporation/mariadb-docs"
SUBDIR="agent-skills"
# Upstream ref to vendor. NOT pinned: defaults to the latest commit on the
# upstream default branch (main). Pass a tag/branch/commit as $1 to sync a
# specific version instead. Either way, the resolved commit SHA is recorded per
# plugin in skills-source.json ("commit").
DEFAULT_REF="main"
REF="${1:-$DEFAULT_REF}"

# Resolve repo root (parent of this scripts/ dir).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Plugins to keep in sync (relative to repo root). All use a flat layout.
# The "dev" plugins vendor every layer; the "sql" plugins vendor only the layers
# in SQL_INCLUDE_LAYERS below.
TARGET_PLUGINS=(
  "claude/dev-plugin"
  "codex/dev-plugin"
  "opencode/dev-plugin"
  "pi/dev-plugin"
)
SQL_PLUGINS=(
  "claude/sql-plugin"
  "codex/sql-plugin"
  "opencode/sql-plugin"
)
# Include keys the sql plugins vendor: the upstream manifest layers
# granular/statements, granular/functions and topical, plus the local
# additional-skills/sql subfolder ("additional-sql"). The additional-skills/rest,
# schema-management and migrator subfolders are omitted from sql (they are
# dev-only), as are the granular/tools + connectors layers. Use
# "additional-<subfolder>" to pick a subfolder, or "additional" for all of them.
SQL_INCLUDE_LAYERS=("granular-statements" "granular-functions" "topical" "additional-sql")

# This repo's own skills, vendored flat into every plugin alongside upstream.
# They are grouped in per-topic subfolders; dev vendors all of them, while the
# sql plugins select a subset (see SQL_INCLUDE_LAYERS). Add a new subfolder here
# to make it selectable via the "additional-<subfolder>" include key.
ADDITIONAL_SKILLS_DIR="$REPO_ROOT/additional-skills"
ADDITIONAL_SUBDIRS=("sql" "rest" "schema-management" "migrator" "laravel")

# The "contributor" plugins vendor a DIFFERENT source: the skills tracked in the
# mariadb-shell repository under .claude/skills/ (no manifest — every SKILL.md
# under it is a skill). That repo is PUBLIC, so no token is needed. One is still
# used when available ($GH_TOKEN, else `gh auth token`) purely for the higher API
# rate limit — and so this keeps working if the repo is ever made private again.
# Override the ref via $CONTRIB_REF.
CONTRIB_REPO="mariadb-corporation/mariadb-shell"
CONTRIB_SUBDIR=".claude/skills"
CONTRIB_REF="${CONTRIB_REF:-main}"
CONTRIB_PLUGINS=(
  "claude/contributor-plugin"
  "codex/contributor-plugin"
  "opencode/contributor-plugin"
)

command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "error: curl is required" >&2; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Fetching $SOURCE_REPO@$REF ..."
curl -fsSL "https://codeload.github.com/$SOURCE_REPO/tar.gz/$REF" \
  | tar -xz -C "$TMP"

# codeload extracts into <repo>-<ref>/ ; locate the agent-skills dir.
SRC_ROOT="$(find "$TMP" -maxdepth 1 -type d -name '*-*' | head -n1)"
SRC_SKILLS="$SRC_ROOT/$SUBDIR"
MANIFEST="$SRC_SKILLS/.skills-manifest.json"
[ -f "$MANIFEST" ] || { echo "error: manifest not found at $MANIFEST" >&2; exit 1; }

# Resolve the concrete commit SHA + baseline once, shared across plugins.
COMMIT="$(curl -s "https://api.github.com/repos/$SOURCE_REPO/commits/$REF" \
  | jq -r '.sha // empty')"
COMMIT="${COMMIT:-$REF}"
BASELINE="$(jq -r '.baseline // "unknown"' "$MANIFEST")"
SYNCED_AT="$(date -u +%Y-%m-%d)"

# Vendor the downloaded skills into a single plugin's skills/ dir (flat layout).
vendor_into() {
  local plugin_dir="$1"; shift
  local skills_dir="$plugin_dir/skills"
  local provenance="$plugin_dir/skills-source.json"

  # Remaining args = INCLUDE keys. Empty = the full dev set: every upstream
  # manifest layer plus every local additional-skills/ subfolder. A non-empty list
  # restricts vendoring to exactly those upstream layer keys, and selects local
  # additional-skills/ subfolders via "additional-<subfolder>" keys (or
  # "additional" for every subfolder).
  local include_json='[]'
  local -a add_subdirs=()
  if [ "$#" -eq 0 ]; then
    add_subdirs=("${ADDITIONAL_SUBDIRS[@]}")
  else
    include_json="$(printf '%s\n' "$@" | jq -R . | jq -s .)"
    if printf '%s\n' "$@" | grep -qx 'additional'; then
      add_subdirs=("${ADDITIONAL_SUBDIRS[@]}")
    else
      local sub
      for sub in "${ADDITIONAL_SUBDIRS[@]}"; do
        if printf '%s\n' "$@" | grep -qx "additional-$sub"; then
          add_subdirs+=("$sub")
        fi
      done
    fi
  fi

  if [ ! -d "$plugin_dir" ]; then
    echo "warning: plugin dir not found, skipping: $plugin_dir" >&2
    return
  fi

  # Reset skills/ (preserve .gitkeep).
  mkdir -p "$skills_dir"
  find "$skills_dir" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf {} +

  # Copy each upstream skill dir flat: skills/<skill>/ regardless of its
  # upstream grouping (OpenCode discovers skills only one level deep, and a flat
  # layout keeps every plugin identical on disk).
  local count=0 name relpath skill_reldir
  while IFS=$'\t' read -r name relpath; do
    if [ ! -f "$SRC_SKILLS/$relpath" ]; then
      echo "warning: missing skill '$name' at $relpath — skipping" >&2
      continue
    fi
    skill_reldir="$(dirname "$relpath")"
    cp -R "$SRC_SKILLS/$skill_reldir" "$skills_dir/$(basename "$skill_reldir")"
    count=$((count + 1))
  done < <(jq -r --argjson include "$include_json" '
      .layers | to_entries[]
      | select(($include | length) == 0 or (.key as $k | $include | index($k)))
      | .value.skills[] | [.name, .path] | @tsv
    ' "$MANIFEST")

  # Copy this repo's local additional-skills/ (flat) from the selected subfolders
  # and collect their manifest entries so the disk<->manifest consistency tests
  # still pass. dev vendors every subfolder; the sql plugins take only "sql".
  local extra_entries="[]" skill_md sdir sname sub base
  if [ "${#add_subdirs[@]}" -gt 0 ]; then
    for sub in "${add_subdirs[@]}"; do
      base="$ADDITIONAL_SKILLS_DIR/$sub"
      [ -d "$base" ] || continue
      while IFS= read -r skill_md; do
        sdir="$(dirname "$skill_md")"
        sname="$(basename "$sdir")"
        cp -R "$sdir" "$skills_dir/$sname"
        count=$((count + 1))
        extra_entries="$(jq \
          --arg n "$sname" \
          --arg p "$sname/SKILL.md" \
          --arg baseline "$BASELINE" \
          '. + [{name: $n, path: $p, status: "local", baseline_version: $baseline}]' \
          <<<"$extra_entries")"
      done < <(find "$base" -mindepth 2 -maxdepth 2 -name SKILL.md | sort)
    done
  fi

  # Write the vendored manifest: flatten every upstream skill `path` to its
  # flattened location (last two segments, e.g.
  # granular/statements/mariadb-x/SKILL.md -> mariadb-x/SKILL.md), and append an
  # "additional" layer for the local skills, so all manifest-driven loaders
  # resolve against the on-disk flat layout.
  jq --argjson extra "$extra_entries" --argjson include "$include_json" '
        .layers |= map_values(
          .skills |= map(.path = (.path | split("/") | .[-2:] | join("/")))
        )
        | if ($include | length) > 0
          then .layers |= with_entries(select(.key as $k | $include | index($k)))
          else . end
        | if ($extra | length) > 0
          then .layers["additional"] = {tier: 3, path: ".", author: "local", skills: $extra}
          else . end
      ' "$MANIFEST" > "$skills_dir/.skills-manifest.json"

  jq -n \
    --arg repo "$SOURCE_REPO" \
    --arg subdir "$SUBDIR" \
    --arg ref "$REF" \
    --arg commit "$COMMIT" \
    --arg baseline "$BASELINE" \
    --arg synced_at "$SYNCED_AT" \
    --argjson count "$count" \
    '{
       source_repo: $repo,
       subdir: $subdir,
       ref: $ref,
       commit: $commit,
       baseline: $baseline,
       skills_synced: $count,
       synced_at: $synced_at
     }' > "$provenance"

  echo "  $plugin_dir: synced $count skills"
}

# Vendor manifest-less contributor skills (every SKILL.md under $src) flat into a
# contributor plugin, writing a synthesized manifest + provenance.
vendor_contributor_into() {
  local plugin_dir="$1" src="$2" commit="$3"
  local skills_dir="$plugin_dir/skills"
  local provenance="$plugin_dir/skills-source.json"

  if [ ! -d "$plugin_dir" ]; then
    echo "warning: plugin dir not found, skipping: $plugin_dir" >&2
    return
  fi

  mkdir -p "$skills_dir"
  find "$skills_dir" -mindepth 1 -maxdepth 1 ! -name '.gitkeep' -exec rm -rf {} +

  local count=0 entries="[]" skill_md sdir sname
  while IFS= read -r skill_md; do
    sdir="$(dirname "$skill_md")"
    sname="$(basename "$sdir")"
    cp -R "$sdir" "$skills_dir/$sname"
    count=$((count + 1))
    entries="$(jq --arg n "$sname" --arg p "$sname/SKILL.md" \
      '. + [{name: $n, path: $p, status: "contributor"}]' <<<"$entries")"
  done < <(find "$src" -mindepth 2 -maxdepth 2 -name SKILL.md | sort)

  jq -n --argjson skills "$entries" \
    '{baseline: "n/a", layers: {contributor: {tier: 0, path: ".", author: "mariadb-shell", skills: $skills}}}' \
    > "$skills_dir/.skills-manifest.json"

  jq -n \
    --arg repo "$CONTRIB_REPO" --arg subdir "$CONTRIB_SUBDIR" \
    --arg ref "$CONTRIB_REF" --arg commit "$commit" \
    --arg synced_at "$SYNCED_AT" --argjson count "$count" \
    '{source_repo: $repo, subdir: $subdir, ref: $ref, commit: $commit,
      skills_synced: $count, synced_at: $synced_at}' > "$provenance"

  echo "  $plugin_dir: synced $count skills"
}

for plugin in "${TARGET_PLUGINS[@]}"; do
  vendor_into "$REPO_ROOT/$plugin"
done

for plugin in "${SQL_PLUGINS[@]}"; do
  vendor_into "$REPO_ROOT/$plugin" "${SQL_INCLUDE_LAYERS[@]}"
done

# Contributor plugins: skills from the mariadb-shell repo, which is public — so
# this no longer depends on having a token, and these plugins no longer drop out
# of an unauthenticated sync (they silently fell a skill behind that way). A token
# is still passed when one happens to be available, for the higher API rate limit
# and so a return to private does not break this. Still best-effort: on any
# failure we warn and leave these plugins untouched.
CONTRIB_SYNCED=0
CONTRIB_TOKEN="${GH_TOKEN:-}"
if [ -z "$CONTRIB_TOKEN" ] && command -v gh >/dev/null 2>&1; then
  CONTRIB_TOKEN="$(gh auth token 2>/dev/null || true)"
fi

# curl with the token only when there is one. A function rather than an array of
# header args: under `set -u`, bash 3.2 (macOS) errors on expanding an empty
# array.
contrib_curl() {
  if [ -n "$CONTRIB_TOKEN" ]; then
    curl -H "Authorization: Bearer $CONTRIB_TOKEN" "$@"
  else
    curl "$@"
  fi
}

if [ -n "$CONTRIB_TOKEN" ]; then
  echo "Fetching $CONTRIB_REPO@$CONTRIB_REF ($CONTRIB_SUBDIR) ..."
else
  echo "Fetching $CONTRIB_REPO@$CONTRIB_REF ($CONTRIB_SUBDIR), unauthenticated ..."
fi
CONTRIB_TMP="$TMP/contrib"
mkdir -p "$CONTRIB_TMP"
if contrib_curl -fsSL \
     -H "Accept: application/vnd.github+json" \
     "https://api.github.com/repos/$CONTRIB_REPO/tarball/$CONTRIB_REF" \
     | tar -xz -C "$CONTRIB_TMP" 2>/dev/null; then
  CONTRIB_SRC_ROOT="$(find "$CONTRIB_TMP" -maxdepth 1 -type d -name '*-*' | head -n1)"
  CONTRIB_SKILLS="$CONTRIB_SRC_ROOT/$CONTRIB_SUBDIR"
  CONTRIB_COMMIT="$(contrib_curl -s \
    "https://api.github.com/repos/$CONTRIB_REPO/commits/$CONTRIB_REF" \
    | jq -r '.sha // empty')"
  CONTRIB_COMMIT="${CONTRIB_COMMIT:-$CONTRIB_REF}"
  if [ -d "$CONTRIB_SKILLS" ]; then
    for plugin in "${CONTRIB_PLUGINS[@]}"; do
      vendor_contributor_into "$REPO_ROOT/$plugin" "$CONTRIB_SKILLS" "$CONTRIB_COMMIT"
    done
    CONTRIB_SYNCED=${#CONTRIB_PLUGINS[@]}
  else
    echo "warning: $CONTRIB_SUBDIR not found in $CONTRIB_REPO@$CONTRIB_REF — skipping contributor plugins" >&2
  fi
else
  echo "warning: failed to fetch $CONTRIB_REPO@$CONTRIB_REF — skipping contributor plugins" >&2
fi

# --- Keep the DevHub's generated skill data in step -------------------------
# docs/ renders its catalog from docs/_data/skills.yml and quotes the skill
# count in prose from docs/_config.yml, both derived from the manifests just
# written. Regenerating here is the only way they cannot go stale — a note in
# CONTRIBUTING.md asking someone to remember is not.
#
# Soft dependency on purpose: every plugin is already vendored and correct by
# this point, so a machine without python3 gets a warning rather than a sync
# that reports failure after doing all its work.
REGEN="$REPO_ROOT/docs/regenerate-skills-data.py"
if [ -f "$REGEN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 "$REGEN" \
      || echo "warning: $REGEN failed — the DevHub's skill data may be stale" >&2
  else
    echo "warning: python3 not found — run 'npm run docs:skills' to refresh the DevHub's skill data" >&2
  fi
fi

total_plugins=$(( ${#TARGET_PLUGINS[@]} + ${#SQL_PLUGINS[@]} ))
echo "Done. Synced $total_plugins plugin(s) from $SOURCE_REPO@$REF" \
     "and $CONTRIB_SYNCED contributor plugin(s) from $CONTRIB_REPO@$CONTRIB_REF."
