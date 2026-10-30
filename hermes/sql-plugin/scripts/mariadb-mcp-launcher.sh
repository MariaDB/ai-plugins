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
# mariadb-mcp-launcher.sh — resolve (installing if needed) and launch the
# mariadb-shell native MCP server.
#
# Resolution order:
#   1. $MARIADB_SHELL_BIN, if set (explicit override).
#   2. A mariadb-shell found on $PATH whose version is >= MARIADB_SHELL_VERSION.
#   3. A local install at $MARIADB_SHELL_BINDIR/mariadb-shell (default
#      ~/.local/bin/mariadb-shell) at that version or newer.
#   4. Otherwise fetch the official installer, install.sh, from a pinned
#      mariadb-shell commit and install release v$MARIADB_SHELL_VERSION — the one
#      this plugin release was tested with, prerelease or not — into
#      ~/.local/share/mariadb-shell/<version>, linked into ~/.local/bin; then
#      launch what it installed.
#
# Installing is delegated to install.sh rather than reimplemented here: it picks
# the package matching the local OS, CPU and glibc version and verifies its
# checksum. The checksums come from mariadb-shell-<tag>.SHA256SUMS next to this
# script, a copy of that release's SHA256SUMS committed with the plugin, so a
# package replaced on the release after the fact is refused. Nothing in this
# launcher needs to know how release assets are named.
#
# This copy is Hermes' own: the other harnesses' launchers install the newest
# release from the installer on main.
#
# However it is resolved, the binary is exec'd as
#   mariadb-shell -- mcp start-server --transport=stdio
# so the MCP server runs over stdio (not HTTP). stdout therefore belongs to the
# MCP transport alone: every message from this script, and from the installer it
# runs, goes to stderr instead. The MCP config just points at this launcher with
# no extra arguments.
#
# Environment:
#   MARIADB_SHELL_VERSION     Minimum acceptable version (default below). A PATH
#                             or locally installed binary is accepted when equal
#                             or higher; anything lower triggers an install of
#                             release v<this version>.
#   MARIADB_SHELL_BIN         Path to a pre-installed binary; skips all other logic.
#   MARIADB_SHELL_BINDIR      Where install.sh links the binary (default ~/.local/bin);
#                             this is also where step 3 looks.
#   MARIADB_SHELL_PREFIX      Passed through: where install.sh unpacks releases.
#   MARIADB_SHELL_TAG         Release tag to install (default v$MARIADB_SHELL_VERSION).
#                             A tag with no committed SHA256SUMS next to this
#                             script is checked against the release's own.
#   MARIADB_SHELL_REPO        Passed through: owner/repo to install from.

set -euo pipefail

VERSION="${MARIADB_SHELL_VERSION:-26.10.4}"
REPO="${MARIADB_SHELL_REPO:-mariadb-corporation/mariadb-shell}"
BINDIR="${MARIADB_SHELL_BINDIR:-$HOME/.local/bin}"
TAG="${MARIADB_SHELL_TAG:-v$VERSION}"
# The mariadb-shell commit the installer is taken from: fixed, so the script
# that runs is the one this launcher was tested with, not whatever main holds.
# Move it only when the installers change in a way the launcher needs.
INSTALLER_COMMIT="664993ccbc523cc82218251fcbe9c2fb8a209cdb"
INSTALLER_URL="https://raw.githubusercontent.com/$REPO/$INSTALLER_COMMIT/install.sh"
SUMS_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/mariadb-shell-$TAG.SHA256SUMS"

# Arguments that start the mariadb-shell MCP server over stdio. Every resolved
# binary (override / PATH / local install / fresh install) is launched with
# exactly these.
MCP_ARGS=(-- mcp start-server --transport=stdio)

log() { echo "mariadb-mcp-launcher: $*" >&2; }
die() { log "error: $*"; exit 1; }

# version_ge A B — succeed (return 0) when dotted-numeric version A >= B.
version_ge() {
  [ "$1" = "$2" ] && return 0
  local -a a b; local i x y len
  IFS=. read -ra a <<<"$1"
  IFS=. read -ra b <<<"$2"
  len=${#a[@]}; [ "${#b[@]}" -gt "$len" ] && len=${#b[@]}
  for ((i = 0; i < len; i++)); do
    x=${a[i]:-0}; y=${b[i]:-0}
    if   ((10#$x > 10#$y)); then return 0
    elif ((10#$x < 10#$y)); then return 1
    fi
  done
  return 0
}

# shell_version BIN — print the version BIN reports, or nothing.
#
# The version line looks like "mariadb-shell   Ver 26.8.0 for macos ...", so the
# number after "Ver" is read first; a bare numeric match is only the fallback,
# since the leading path may itself carry digits.
shell_version() {
  local out ver
  out="$("$1" --version 2>/dev/null | head -n1 || true)"
  [ -n "$out" ] || return 0
  ver="$(printf '%s\n' "$out" | grep -oiE 'ver[[:space:]]+[0-9]+(\.[0-9]+)+' | head -n1 | grep -oE '[0-9]+(\.[0-9]+)+' || true)"
  [ -n "$ver" ] || ver="$(printf '%s\n' "$out" | grep -oE '[0-9]+(\.[0-9]+)+' | head -n1 || true)"
  printf '%s' "$ver"
}

# Escape hatch: use an explicitly provided binary.
if [ -n "${MARIADB_SHELL_BIN:-}" ]; then
  [ -x "$MARIADB_SHELL_BIN" ] || die "MARIADB_SHELL_BIN is not executable: $MARIADB_SHELL_BIN"
  exec "$MARIADB_SHELL_BIN" "${MCP_ARGS[@]}"
fi

# Prefer a mariadb-shell already on PATH when it meets the required version.
if PATH_BIN="$(command -v mariadb-shell 2>/dev/null)" && [ -n "$PATH_BIN" ]; then
  PATH_VER="$(shell_version "$PATH_BIN")"
  if [ -n "$PATH_VER" ] && version_ge "$PATH_VER" "$VERSION"; then
    log "using mariadb-shell $PATH_VER from PATH: $PATH_BIN (>= required $VERSION)"
    exec "$PATH_BIN" "${MCP_ARGS[@]}"
  fi
  log "mariadb-shell on PATH (${PATH_VER:-unknown version}) does not meet required $VERSION; looking for a managed install"
fi

# --- Where a managed install lives -------------------------------------------
# Git-Bash/MSYS is a Windows host: install.sh refuses to run there (there is no
# glibc/macOS package to pick), and install.ps1 shims the binary under
# %LOCALAPPDATA% as a .cmd. Look there, but leave installing to the .cmd launcher.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) WINDOWS=1 ;;
  *)                    WINDOWS=0 ;;
esac

if [ "$WINDOWS" = 1 ]; then
  LOCAL_BIN="${LOCALAPPDATA:-$HOME/AppData/Local}/Programs/mariadb-shell/bin/mariadb-shell.cmd"
else
  LOCAL_BIN="$BINDIR/mariadb-shell"
fi

# --- Step 3: an existing local install ---------------------------------------
if [ -x "$LOCAL_BIN" ]; then
  LOCAL_VER="$(shell_version "$LOCAL_BIN")"
  if [ -n "$LOCAL_VER" ] && version_ge "$LOCAL_VER" "$VERSION"; then
    log "using installed mariadb-shell $LOCAL_VER: $LOCAL_BIN (>= required $VERSION)"
    exec "$LOCAL_BIN" "${MCP_ARGS[@]}"
  fi
  log "installed mariadb-shell (${LOCAL_VER:-unknown version}) at $LOCAL_BIN does not meet required $VERSION; installing $TAG"
fi

if [ "$WINDOWS" = 1 ]; then
  die "no mariadb-shell at $LOCAL_BIN.
  This launcher does not install on Windows — install.sh has no Windows package.
  Either run scripts/mariadb-mcp-launcher.cmd instead (it uses install.ps1), or
  install once by hand:
      \$env:MARIADB_SHELL_TAG = '$TAG'
      irm https://github.com/$REPO/raw/$INSTALLER_COMMIT/install.ps1 | iex"
fi

# --- Step 4: install the pinned release --------------------------------------
# mariadb-shell is public: nothing here sends credentials, and nothing reads
# another tool's stored login.
if command -v curl >/dev/null 2>&1; then
  fetch() { curl -fsSL --retry 3 -o "$2" "$1"; }
elif command -v wget >/dev/null 2>&1; then
  fetch() { wget -q -O "$2" "$1"; }
else
  die "neither curl nor wget is available; cannot fetch the mariadb-shell installer"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# A tag the plugin carries no SHA256SUMS for was chosen by whoever set
# MARIADB_SHELL_TAG or MARIADB_SHELL_VERSION; that release's own is used then.
if [ -f "$SUMS_FILE" ]; then
  SUMS="$SUMS_FILE"
else
  SUMS=""
  log "no committed checksums for $TAG; checking against the release's own SHA256SUMS"
fi

install_failed=0
# run_installer — install, with output kept off stdout.
#
# BINDIR is exported so the installer links where step 3 looks. A pinned tag
# needs no prerelease handling: the installer takes a named release whether or
# not it is a prerelease. Its own progress output would corrupt the MCP stream,
# hence the redirect to stderr.
run_installer() {
  MARIADB_SHELL_BINDIR="$BINDIR" \
  MARIADB_SHELL_TAG="$TAG" \
  MARIADB_SHELL_SHA256SUMS="$SUMS" \
  sh "$TMP/install.sh" >&2
}

log "no suitable mariadb-shell found; installing $TAG from $REPO ..."
# A harness that stops waiting for the server (Claude Code gives up after 30 s
# unless MCP_TIMEOUT is raised) signals this script, but the installer it runs
# finishes regardless — so say how to pick the install up afterwards.
log "a first install can take a minute. If the harness gives up on this server meanwhile (Claude Code waits 30 s unless MCP_TIMEOUT is raised), the install still finishes: reconnect the server then (/mcp in Claude Code), or start a new session."
if fetch "$INSTALLER_URL" "$TMP/install.sh"; then
  run_installer || { install_failed=1; log "the mariadb-shell installer failed"; }
else
  install_failed=1
  log "could not download the installer from $INSTALLER_URL"
fi

# A concurrent launcher may have completed the install that this one lost the
# race for, so the binary — not the installer's exit status — is the last word.
if [ ! -x "$LOCAL_BIN" ]; then
  die "no mariadb-shell at $LOCAL_BIN after installing.
  Install it by hand and retry, or point MARIADB_SHELL_BIN at an existing binary:
      curl -fsSLo install.sh https://github.com/$REPO/raw/$INSTALLER_COMMIT/install.sh
      MARIADB_SHELL_TAG=$TAG bash install.sh"
fi
[ "$install_failed" = 0 ] || log "using the mariadb-shell already present at $LOCAL_BIN"

# Below the required version is worth saying, but not worth refusing to start
# over: a MARIADB_SHELL_TAG older than the floor was asked for by name.
NEW_VER="$(shell_version "$LOCAL_BIN")"
if [ -n "$NEW_VER" ] && ! version_ge "$NEW_VER" "$VERSION"; then
  log "warning: installed mariadb-shell $NEW_VER is below the required $VERSION; starting it anyway"
fi

log "starting mariadb-shell ${NEW_VER:-} MCP server: $LOCAL_BIN"
exec "$LOCAL_BIN" "${MCP_ARGS[@]}"
