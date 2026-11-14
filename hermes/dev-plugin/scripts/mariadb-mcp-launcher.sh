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
# Step 4 is serialized: launchers started together (several sessions, or the
# MCP and another harness at once) take turns through a lock folder in the
# install prefix, and wait for an install.sh that is already running there. The
# one that waited looks again before installing, since the install it waited
# for has usually put a good enough shell in place.
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
#   MARIADB_SHELL_PREFIX      Passed through: where install.sh unpacks releases
#                             (default ~/.local/share/mariadb-shell). The
#                             launchers' lock folder, .mcp-launcher.lock, is there.
#   MARIADB_SHELL_LOCK_WAIT   Seconds to wait for another install to finish
#                             (default 180) before giving up on installing.
#   MARIADB_SHELL_TAG         Release tag to install (default v$MARIADB_SHELL_VERSION).
#                             A tag with no committed SHA256SUMS next to this
#                             script is checked against the release's own.
#   MARIADB_SHELL_REPO        Passed through: owner/repo to install from.
#   MARIADB_RESTD_TAG         Passed on to the MCP server: the mariadb-restd release it
#                             installs (default v$MARIADB_RESTD_VERSION), with
#                             mariadb-restd-<tag>.SHA256SUMS from next to this script.
#   MARIADB_RESTD_VERSION     Passed on to the MCP server: the lowest mariadb-restd
#                             its restd.configure_restd accepts when the agent names
#                             none (default below). An older one is passed over and
#                             the newest release installed.

set -euo pipefail

VERSION="${MARIADB_SHELL_VERSION:-26.11.2}"
# The MCP server reads this, not the launcher: the floor for the mariadb-restd it
# installs, kept beside the shell's by scripts/set-mariadb-restd-version.sh.
export MARIADB_RESTD_VERSION="${MARIADB_RESTD_VERSION:-26.11.0}"
REPO="${MARIADB_SHELL_REPO:-mariadb-corporation/mariadb-shell}"
BINDIR="${MARIADB_SHELL_BINDIR:-$HOME/.local/bin}"
# install.sh's own default, so the lock sits beside the installs it guards.
PREFIX="${MARIADB_SHELL_PREFIX:-$HOME/.local/share/mariadb-shell}"
LOCK_WAIT="${MARIADB_SHELL_LOCK_WAIT:-180}"
case "$LOCK_WAIT" in
  ''|*[!0-9]*) echo "mariadb-mcp-launcher: MARIADB_SHELL_LOCK_WAIT is not a number of seconds: $LOCK_WAIT; using 180" >&2; LOCK_WAIT=180 ;;
esac
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

# mariadb-restd is pinned as the shell is: the MCP server installs exactly
# MARIADB_RESTD_TAG (default v<restd floor>) with the install script at that
# tag, checked against the copy of that release's SHA256SUMS committed next to
# this script. A tag the plugin carries none for is checked against the
# release's own. The launcher only exports these; the MCP server reads them.
export MARIADB_RESTD_TAG="${MARIADB_RESTD_TAG:-v$MARIADB_RESTD_VERSION}"
RESTD_SUMS_FILE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/mariadb-restd-$MARIADB_RESTD_TAG.SHA256SUMS"
if [ -f "$RESTD_SUMS_FILE" ]; then
  export MARIADB_RESTD_SHA256SUMS="$RESTD_SUMS_FILE"
else
  unset MARIADB_RESTD_SHA256SUMS
  log "no committed checksums for mariadb-restd $MARIADB_RESTD_TAG; an install checks it against the release's own SHA256SUMS"
fi

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
# The version line looks like "mariadb-shell   Ver 26.8.0 for macos ...", but a
# build can print other messages (plugin registration errors) before it, so the
# whole output is searched for "Ver <number>". A bare number on the first line
# is only the fallback, since the leading path may itself carry digits.
shell_version() {
  local out ver
  out="$("$1" --version 2>/dev/null || true)"
  [ -n "$out" ] || return 0
  ver="$(printf '%s\n' "$out" | grep -oiE '(^|[^[:alnum:]])ver[[:space:]]+[0-9]+(\.[0-9]+)+' | head -n1 | grep -oE '[0-9]+(\.[0-9]+)+' || true)"
  [ -n "$ver" ] || ver="$(printf '%s\n' "$out" | head -n1 | grep -oE '[0-9]+(\.[0-9]+)+' | head -n1 || true)"
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

# A tag the plugin carries no SHA256SUMS for was chosen by whoever set
# MARIADB_SHELL_TAG or MARIADB_SHELL_VERSION; that release's own is used then.
if [ -f "$SUMS_FILE" ]; then
  SUMS="$SUMS_FILE"
else
  SUMS=""
  log "no committed checksums for $TAG; checking against the release's own SHA256SUMS"
fi

# --- Taking turns ------------------------------------------------------------
# Installers running at once into one prefix all unpack the same tarball into
# the same folder, and all of them fail. So the launchers queue on a lock
# folder (mkdir is atomic everywhere; macOS has no flock) holding the PIDs of
# the launcher and of the installer it runs. The lock is stale once none of
# them is alive. A launcher the harness stops waiting for leaves the lock to
# its installer, which carries on, so the next launcher waits for that install
# instead of starting a second one.
#
# INSTALL_LOCK is install.sh's own lock (in versions that have one): an install
# someone else started, a VS Code extension for instance, is waited for too.
LOCK="$PREFIX/.mcp-launcher.lock"
INSTALL_LOCK="$PREFIX/.install.lock"
HAVE_LOCK=0
INSTALLER_PID=""
TMP=""

# cleanup — remove the temp folder and give the lock back. Runs on exit, and
# before exec: an exec'd server keeps this PID, which would hold the lock forever.
cleanup() {
  [ -z "$TMP" ] || rm -rf "$TMP"
  TMP=""
  if [ "$HAVE_LOCK" = 1 ]; then
    if [ -z "$INSTALLER_PID" ] || ! kill -0 "$INSTALLER_PID" 2>/dev/null; then
      rm -rf "$LOCK"
    fi
    HAVE_LOCK=0
  fi
}
trap cleanup EXIT
# A trapped signal also interrupts `wait`, so the EXIT trap above runs at once.
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# launch BIN — start BIN as the MCP server, releasing the lock first.
launch() {
  cleanup
  trap - EXIT HUP INT TERM
  exec "$1" "${MCP_ARGS[@]}"
}

# good_shell — print a mariadb-shell >= VERSION from step 2 or 3, or nothing.
good_shell() {
  local bin ver prev=''
  for bin in "$(command -v mariadb-shell 2>/dev/null || true)" "$LOCAL_BIN"; do
    [ -n "$bin" ] && [ -x "$bin" ] && [ "$bin" != "$prev" ] || continue
    prev="$bin"
    ver="$(shell_version "$bin")"
    if [ -n "$ver" ] && version_ge "$ver" "$VERSION"; then
      printf '%s' "$bin"
      return 0
    fi
  done
}

# lock_busy DIR — succeed while the lock folder DIR belongs to a live install:
# one of the PIDs in its files runs, or it has no PID yet and is under a minute
# old (its owner is between mkdir and writing the PID).
lock_busy() {
  local pid pids
  [ -d "$1" ] || return 1
  pids="$(cat "$1"/* 2>/dev/null | tr -cs '0-9' ' ' || true)"
  for pid in $pids; do
    kill -0 "$pid" 2>/dev/null && return 0
  done
  [ -z "${pids// /}" ] && [ -z "$(find "$1" -maxdepth 0 -mmin +1 2>/dev/null)" ]
}

# take_turn — wait until no other install runs, then hold LOCK. Returns 1 when
# LOCK_WAIT runs out first. Without a usable prefix it goes ahead unlocked.
take_turn() {
  local start=$SECONDS next_note=0 who='' waited
  mkdir -p "$PREFIX" 2>/dev/null || true
  while :; do
    if lock_busy "$INSTALL_LOCK"; then
      who="an install already running ($INSTALL_LOCK)"
    elif mkdir "$LOCK" 2>/dev/null; then
      echo "$$" >"$LOCK/pid"
      HAVE_LOCK=1
      return 0
    elif [ ! -d "$LOCK" ]; then
      log "cannot create the lock $LOCK; installing without it"
      return 0
    elif lock_busy "$LOCK"; then
      who="another MCP launcher's install (lock $LOCK)"
    else
      # Renamed, not removed, so only one waiter clears it.
      log "clearing a lock left by an install that is gone: $LOCK"
      mv "$LOCK" "$LOCK.stale.$$" 2>/dev/null && rm -rf "$LOCK.stale.$$"
      continue
    fi
    waited=$((SECONDS - start))
    if [ "$waited" -ge "$LOCK_WAIT" ]; then
      log "gave up after ${waited}s waiting for $who"
      return 1
    fi
    if [ "$waited" -ge "$next_note" ]; then
      if [ "$next_note" = 0 ]; then
        log "waiting for $who to finish (up to ${LOCK_WAIT}s, MARIADB_SHELL_LOCK_WAIT)"
      else
        log "still waiting for $who (${waited}s)"
      fi
      next_note=$((waited + 10))
    fi
    sleep 1
  done
}

install_failed=0
# run_installer — install, with output kept off stdout.
#
# BINDIR is exported so the installer links where step 3 looks. A pinned tag
# needs no prerelease handling: the installer takes a named release whether or
# not it is a prerelease. Its own progress output would corrupt the MCP stream,
# hence the redirect to stderr. It runs in the background only so that its PID
# can go into the lock.
run_installer() {
  local rc=0
  MARIADB_SHELL_BINDIR="$BINDIR" \
  MARIADB_SHELL_TAG="$TAG" \
  MARIADB_SHELL_SHA256SUMS="$SUMS" \
  sh "$TMP/install.sh" >&2 &
  INSTALLER_PID=$!
  [ "$HAVE_LOCK" = 0 ] || echo "$INSTALLER_PID" >>"$LOCK/pid"
  wait "$INSTALLER_PID" || rc=$?
  INSTALLER_PID=""
  return "$rc"
}

# A harness that stops waiting for the server (Claude Code gives up after 30 s
# unless MCP_TIMEOUT is raised) signals this script, but the installer it runs
# finishes regardless — so say how to pick the install up afterwards.
log "a first install can take a minute. If the harness gives up on this server meanwhile (Claude Code waits 30 s unless MCP_TIMEOUT is raised), the install still finishes: reconnect the server then (/mcp in Claude Code), or start a new session."
if ! take_turn; then
  install_failed=1
else
  # Whoever held the lock before may have installed a good enough shell.
  BIN="$(good_shell)"
  if [ -n "$BIN" ]; then
    log "using mariadb-shell $(shell_version "$BIN") installed meanwhile: $BIN (>= required $VERSION)"
    launch "$BIN"
  fi

  log "no suitable mariadb-shell found; installing $TAG from $REPO ..."
  TMP="$(mktemp -d)"
  if fetch "$INSTALLER_URL" "$TMP/install.sh"; then
    run_installer || { install_failed=1; log "the mariadb-shell installer failed"; }
  else
    install_failed=1
    log "could not download the installer from $INSTALLER_URL"
  fi
fi

# The version decides, not the installer's exit status: another install may
# have finished meanwhile, and an old shell at LOCAL_BIN is no sign that one did.
BIN="$(good_shell)"
if [ -n "$BIN" ]; then
  [ "$install_failed" = 0 ] || log "using mariadb-shell $(shell_version "$BIN") that another install put in place: $BIN"
  log "starting mariadb-shell $(shell_version "$BIN") MCP server: $BIN"
  launch "$BIN"
fi

if [ ! -x "$LOCAL_BIN" ]; then
  die "no mariadb-shell at $LOCAL_BIN after installing.
  Install it by hand and retry, or point MARIADB_SHELL_BIN at an existing binary:
      curl -fsSLo install.sh https://github.com/$REPO/raw/$INSTALLER_COMMIT/install.sh
      MARIADB_SHELL_TAG=$TAG bash install.sh"
fi

# Below the required version is worth saying, but not worth refusing to start
# over: a MARIADB_SHELL_TAG older than the floor was asked for by name — or,
# after a failed install, it is the only shell there is.
NEW_VER="$(shell_version "$LOCAL_BIN")"
if [ "$install_failed" = 1 ]; then
  log "warning: no mariadb-shell >= $VERSION could be installed; starting the ${NEW_VER:-unknown} version at $LOCAL_BIN anyway"
elif [ -n "$NEW_VER" ]; then
  log "warning: installed mariadb-shell $NEW_VER is below the required $VERSION; starting it anyway"
fi

log "starting mariadb-shell ${NEW_VER:-} MCP server: $LOCAL_BIN"
launch "$LOCAL_BIN"
