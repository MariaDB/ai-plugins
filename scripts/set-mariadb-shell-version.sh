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
# set-mariadb-shell-version.sh — pin the mariadb-shell MCP server version across
# every plugin in this repo.
#
# Updates the MARIADB_SHELL_VERSION value in each plugin's MCP config
# (.mcp.json / opencode.json, and the entries the setup-*-mcp scripts write for
# codex and pi) AND
# the fallback default baked into the launcher scripts (mariadb-mcp-launcher.sh/
# .cmd), for both the dev-* and sql-* plugins across
# claude/, codex/, opencode/ and pi/ — plus `shell_floor` in docs/_config.yml,
# which is where the DevHub quotes the floor in prose.
# Keeping all of them on the same version means every plugin accepts the same
# binary (see scripts/mariadb-mcp-launcher.sh — the version is the minimum each
# plugin will run, so one version == one shared install rather than one install
# per plugin).
#
# This is the mariadb-shell *binary* version, NOT the plugin package version —
# use scripts/set-plugin-version.sh for the latter.
#
# Usage:
#   scripts/set-mariadb-shell-version.sh <version>
#   scripts/set-mariadb-shell-version.sh 26.8.1
#   scripts/set-mariadb-shell-version.sh --help

set -euo pipefail

usage() {
  cat <<'USAGE'
set-mariadb-shell-version.sh — pin the mariadb-shell MCP server version across
every plugin in this repo.

Usage:
  scripts/set-mariadb-shell-version.sh <version>
  scripts/set-mariadb-shell-version.sh --help

Arguments:
  <version>   The mariadb-shell binary version to require, e.g. 26.8.1. This is
              a *minimum*: each launcher accepts any install at or above it.

Updates, across claude/, codex/, opencode/ and pi/:
  - MARIADB_SHELL_VERSION in each plugin's MCP config (.mcp.json, opencode.json)
  - the fallback default in the launchers (mariadb-mcp-launcher.sh / .cmd)
  - the version the setup-*-mcp scripts write (codex, pi)
  - the MARIADB_SHELL_VERSION shown in each plugin README

This is the mariadb-shell *binary* version, NOT the plugin package version —
use scripts/set-plugin-version.sh for the latter.
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

# Reject anything that is not version-shaped rather than writing it into 36
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

# Collect the files that carry the version: launcher scripts (all variants) and
# the MCP config files, across every *-plugin dir (excludes *-plugin-test dirs).
files=()
while IFS= read -r f; do files+=("$f"); done < <(
  find "$REPO_ROOT"/claude/*-plugin \
       "$REPO_ROOT"/codex/*-plugin \
       "$REPO_ROOT"/opencode/*-plugin \
       "$REPO_ROOT"/pi/*-plugin \
       -type f \( \
         -name 'mariadb-mcp-launcher.sh' -o \
         -name 'mariadb-mcp-launcher.cmd' -o \
         -name 'setup-codex-mcp.sh' -o \
         -name 'setup-codex-mcp.cmd' -o \
         -name '.mcp.json' -o \
         -name 'opencode.json' -o \
         -name 'README.md' \
       \) | sort
)

[ "${#files[@]}" -gt 0 ] || { echo "error: no plugin files found under $REPO_ROOT" >&2; exit 1; }

# The DevHub quotes the floor in prose from this key, so it is a version site
# like any other. It lives outside the plugin dirs, hence the separate append —
# this script's reach has lagged a new version site four times now (pi, the
# *_disabled launchers, the setup-codex-mcp scripts, and this), so check it
# whenever a file gains one.
DOCS_CONFIG="$REPO_ROOT/docs/_config.yml"
[ -f "$DOCS_CONFIG" ] && files+=("$DOCS_CONFIG")

# Shapes the version appears in:
#   JSON MCP config / README example:  "MARIADB_SHELL_VERSION": "<v>"
#   bash launcher:                     VERSION="${MARIADB_SHELL_VERSION:-<v>}"
#   cmd launcher:                      set "MARIADB_SHELL_VERSION=<v>"
#   README prose:                      `MARIADB_SHELL_VERSION` (default `<v>`)
#   docs/_config.yml:                  shell_floor: "<v>"
V="$VERSION" perl -i -pe '
  my $v = $ENV{V};
  s/("MARIADB_SHELL_VERSION"\s*:\s*")[^"]*(")/${1}${v}${2}/g;
  s/(MARIADB_SHELL_VERSION:-)[^}]*(\})/${1}${v}${2}/g;
  s/(set "MARIADB_SHELL_VERSION=)[^"]*(")/${1}${v}${2}/g;
  s/^(SHELL_VERSION=")[^"]*(")/${1}${v}${2}/g;
  s/(MARIADB_SHELL_VERSION` \(default `)[^`]*(`\))/${1}${v}${2}/g;
  s/^(shell_floor:\s*")[^"]*(")/${1}${v}${2}/g;
' "${files[@]}"

echo "Set MARIADB_SHELL_VERSION -> $VERSION in ${#files[@]} file(s):"
grep -rn 'SHELL_VERSION\|shell_floor' "${files[@]}" \
  | grep -E "\-${VERSION}\}|=\"?${VERSION}\"|: \"${VERSION}\"" \
  | sed 's/^/  /'
