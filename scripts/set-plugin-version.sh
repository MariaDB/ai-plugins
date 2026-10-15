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
# set-plugin-version.sh — set the plugin package version across every plugin in
# this repo.
#
# Updates the "version" field in each plugin manifest (.claude-plugin/plugin.json,
# .codex-plugin/plugin.json and Hermes' plugin.json) and the "Version **x.y.z**"
# line in each plugin README, for the dev-*, sql-* and contributor-* plugins
# across claude/, codex/, opencode/, pi/ and hermes/, plus the repo-root
# package.json.
#
# Not every plugin carries both: OpenCode has no manifest version field, so only
# its README is updated, and pi has no per-plugin manifest at all — the repo-root
# package.json IS its manifest, which is why that file is in the list.
# (CHANGELOG history is intentionally left untouched.)
#
# This is the plugin *package* version, NOT the mariadb-shell binary version —
# use scripts/set-mariadb-shell-version.sh for the latter.
#
# Usage:
#   scripts/set-plugin-version.sh <version>
#   scripts/set-plugin-version.sh 26.8.1
#   scripts/set-plugin-version.sh --help

set -euo pipefail

usage() {
  cat <<'USAGE'
set-plugin-version.sh — set the plugin package version across every plugin in
this repo.

Usage:
  scripts/set-plugin-version.sh <version>
  scripts/set-plugin-version.sh --help

Arguments:
  <version>   The plugin package version to set, e.g. 26.8.1.

Updates, for the dev-*, sql-* and contributor-* plugins across claude/, codex/,
opencode/, pi/ and hermes/:
  - the "version" field in each plugin manifest (.claude-plugin/plugin.json,
    .codex-plugin/plugin.json, hermes/*-plugin/plugin.json)
  - the "Version **x.y.z**" line in each plugin README
  - the repo-root package.json

Not every plugin carries both: OpenCode has no manifest version field, so only
its README is updated, and pi has no per-plugin manifest at all — the repo-root
package.json IS its manifest. CHANGELOG history is intentionally left untouched.

This is the plugin *package* version, NOT the mariadb-shell binary version —
use scripts/set-mariadb-shell-version.sh for the latter.
USAGE
}

case "${1:-}" in
  -h | --help | help)
    usage
    exit 0
    ;;
esac

VERSION="${1:-}"
if [ -z "$VERSION" ]; then
  echo "error: no version given" >&2
  echo >&2
  usage >&2
  exit 1
fi

# Reject anything that is not version-shaped rather than writing it into 23
# files. A mistyped flag used to be accepted as the version and substituted
# everywhere, which is a tedious thing to undo.
case "$VERSION" in
  -*)
    echo "error: unknown option '$VERSION' (see --help)" >&2
    exit 1
    ;;
esac
if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+(\.[0-9]+)*(-[0-9A-Za-z.]+)?$'; then
  echo "error: '$VERSION' is not a version (expected digits and dots, e.g. 26.8.1)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

command -v perl >/dev/null 2>&1 || { echo "error: perl is required" >&2; exit 1; }

# Collect manifests and READMEs across every *-plugin dir (excludes test dirs),
# then the repo-root package.json — pi's manifest, which lives outside them all.
files=()
while IFS= read -r f; do files+=("$f"); done < <(
  find "$REPO_ROOT"/claude/*-plugin \
       "$REPO_ROOT"/codex/*-plugin \
       "$REPO_ROOT"/opencode/*-plugin \
       "$REPO_ROOT"/pi/*-plugin \
       "$REPO_ROOT"/hermes/*-plugin \
       -type f \( -name 'plugin.json' -o -name 'README.md' \) | sort
)
files+=("$REPO_ROOT/package.json")

[ "${#files[@]}" -gt 0 ] || { echo "error: no plugin files found under $REPO_ROOT" >&2; exit 1; }

# Two shapes the version appears in:
#   plugin manifest JSON:  "version": "<v>"
#   README header line:    Version **<v>**
#
# The JSON substitution is anchored to the start of a line so it can only ever
# hit a "version" key that stands on its own — package.json also carries
# dependency and peerDependency version ranges, and those must not be touched.
V="$VERSION" perl -i -pe '
  my $v = $ENV{V};
  s/^(\s*"version"\s*:\s*")[^"]*(")/${1}${v}${2}/;
  s/^(Version \*\*)[^*]*(\*\*)$/${1}${v}${2}/;
' "${files[@]}"

echo "Set plugin version -> $VERSION in ${#files[@]} file(s):"
grep -rnE "\"version\": \"${VERSION}\"|^Version \*\*${VERSION}\*\*" "${files[@]}" \
  | sed 's/^/  /'
