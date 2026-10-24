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
# mariadb-lsp-launcher.sh — find and launch mariadb-lsp, the MariaDB SQL
# language server that ships in the mariadb-shell package.
#
# This launcher NEVER installs anything. Installing mariadb-shell is the job of
# mariadb-mcp-launcher.sh alone, so that a harness starting the MCP server and
# the language server at the same time downloads the package once, not twice.
# When no suitable mariadb-shell is present yet, this script waits for the MCP
# launcher's install to land (MARIADB_LSP_WAIT seconds), then gives up.
#
# mariadb-lsp has a version of its own (lsp-server's), so it is not compared
# with MARIADB_SHELL_VERSION. Instead the mariadb-shell is resolved exactly as
# the MCP launcher resolves it, and the mariadb-lsp packaged with THAT shell is
# used — the same pairing mariadb-shell's own MCP server relies on:
#
#   1. $MARIADB_LSP_BIN, if set (explicit override).
#   2. The mariadb-shell the MCP launcher would run: $MARIADB_SHELL_BIN, else a
#      mariadb-shell on $PATH at >= MARIADB_SHELL_VERSION, else
#      $MARIADB_SHELL_BINDIR/mariadb-shell (default ~/.local/bin) at that
#      version — and the mariadb-lsp beside it: next to the link, or next to
#      the binary the link points into (install.sh links both from
#      ~/.local/share/mariadb-shell/<version>/bin).
#   3. No such shell yet: wait for the MCP launcher to install one, then 2.
#   4. A shell without mariadb-lsp (the native .deb/.rpm packages are built
#      without it): any mariadb-lsp on $PATH or in $MARIADB_SHELL_BINDIR.
#
# It is exec'd as
#   mariadb-lsp lsp [args passed to this script...]
# which speaks LSP over stdin and stdout, so every message from this script
# goes to stderr.
#
# Environment:
#   MARIADB_SHELL_VERSION  Minimum mariadb-shell version (default below), the
#                          same floor the MCP launcher applies.
#   MARIADB_SHELL_BIN      As for the MCP launcher: the shell to pair with.
#   MARIADB_SHELL_BINDIR   Where install.sh links the binaries (~/.local/bin).
#   MARIADB_LSP_BIN        Path to a mariadb-lsp; skips all other logic.
#   MARIADB_LSP_WAIT       Seconds to wait for the MCP launcher's install
#                          (default 180; 0 does not wait).

set -euo pipefail

VERSION="${MARIADB_SHELL_VERSION:-26.10.4}"
BINDIR="${MARIADB_SHELL_BINDIR:-$HOME/.local/bin}"
WAIT="${MARIADB_LSP_WAIT:-180}"
case "$WAIT" in
  ''|*[!0-9]*) echo "mariadb-lsp-launcher: MARIADB_LSP_WAIT is not a number of seconds: $WAIT; using 180" >&2; WAIT=180 ;;
esac

# Arguments that start the language server over stdio, followed by any given
# to this script (--log FILE, --threads N, ...).
LSP_ARGS=(lsp "$@")

log() { echo "mariadb-lsp-launcher: $*" >&2; }
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

# shell_version BIN — print the version BIN reports, or nothing. Same parsing
# as the MCP launcher: the number after "Ver" first, a bare number otherwise.
shell_version() {
  local out ver
  out="$("$1" --version 2>/dev/null | head -n1 || true)"
  [ -n "$out" ] || return 0
  ver="$(printf '%s\n' "$out" | grep -oiE 'ver[[:space:]]+[0-9]+(\.[0-9]+)+' | head -n1 | grep -oE '[0-9]+(\.[0-9]+)+' || true)"
  [ -n "$ver" ] || ver="$(printf '%s\n' "$out" | grep -oE '[0-9]+(\.[0-9]+)+' | head -n1 || true)"
  printf '%s' "$ver"
}

# resolve PATH — follow symlinks to the file itself (no `realpath -e` on older
# macOS, no `readlink -f` on BSD).
resolve() {
  local p="$1" t
  while [ -L "$p" ]; do
    t="$(readlink "$p")"
    case "$t" in
      /*) p="$t" ;;
      *)  p="$(dirname "$p")/$t" ;;
    esac
  done
  printf '%s' "$p"
}

# lsp_beside SHELL — print the mariadb-lsp packaged with SHELL, or nothing:
# beside the path itself first, then beside the file a link points to.
lsp_beside() {
  local d
  for d in "$(dirname "$1")" "$(dirname "$(resolve "$1")")"; do
    if [ -x "$d/mariadb-lsp" ]; then
      printf '%s' "$d/mariadb-lsp"
      return 0
    fi
  done
}

# find_shell — print the mariadb-shell the MCP launcher would run, or nothing.
find_shell() {
  local bin ver prev=
  if [ -n "${MARIADB_SHELL_BIN:-}" ]; then
    [ -x "$MARIADB_SHELL_BIN" ] && printf '%s' "$MARIADB_SHELL_BIN"
    return 0
  fi
  # With $BINDIR on PATH (the usual setup) both candidates are one file: ask it
  # for its version once.
  for bin in "$(command -v mariadb-shell 2>/dev/null || true)" "$BINDIR/mariadb-shell"; do
    [ -n "$bin" ] && [ -x "$bin" ] && [ "$bin" != "$prev" ] || continue
    prev="$bin"
    ver="$(shell_version "$bin")"
    if [ -n "$ver" ] && version_ge "$ver" "$VERSION"; then
      printf '%s' "$bin"
      return 0
    fi
  done
}

start() {
  log "starting $1"
  exec "$1" "${LSP_ARGS[@]}"
}

# --- 1. Escape hatch: explicit binary ----------------------------------------
if [ -n "${MARIADB_LSP_BIN:-}" ]; then
  [ -x "$MARIADB_LSP_BIN" ] || die "MARIADB_LSP_BIN is not executable: $MARIADB_LSP_BIN"
  exec "$MARIADB_LSP_BIN" "${LSP_ARGS[@]}"
fi

# --- 2./3. The shell the MCP launcher runs, waiting for its install ----------
# With $MARIADB_SHELL_BIN set the MCP launcher never installs, so there is
# nothing to wait for.
SHELL_BIN="$(find_shell)"
if [ -z "$SHELL_BIN" ] && [ -z "${MARIADB_SHELL_BIN:-}" ] && [ "$WAIT" -gt 0 ]; then
  log "no mariadb-shell >= $VERSION yet; waiting up to ${WAIT}s for the MCP server's launcher to install it"
  deadline=$((SECONDS + WAIT))
  while [ -z "$SHELL_BIN" ] && [ "$SECONDS" -lt "$deadline" ]; do
    sleep 2
    SHELL_BIN="$(find_shell)"
  done
fi

if [ -n "$SHELL_BIN" ]; then
  LSP_BIN="$(lsp_beside "$SHELL_BIN")"
  [ -z "$LSP_BIN" ] || start "$LSP_BIN"
  log "the mariadb-shell at $SHELL_BIN has no mariadb-lsp beside it"
fi

# --- 4. Any mariadb-lsp at all -------------------------------------------------
for LSP_BIN in "$(command -v mariadb-lsp 2>/dev/null || true)" "$BINDIR/mariadb-lsp"; do
  if [ -n "$LSP_BIN" ] && [ -x "$LSP_BIN" ]; then
    [ -n "$SHELL_BIN" ] || log "warning: no mariadb-shell >= $VERSION found; using the mariadb-lsp present"
    start "$LSP_BIN"
  fi
done

die "no mariadb-lsp found.
  It ships in the mariadb-shell packages from $VERSION on, which the MariaDB MCP
  server's launcher installs into $BINDIR on its first start. Start a session
  with the plugin's MCP server enabled, or install by hand:
      curl -fsSLo install.sh https://github.com/mariadb-corporation/mariadb-shell/raw/main/install.sh
      bash install.sh
  The native .deb and .rpm packages do not include mariadb-lsp yet. To use a
  binary of your own, set MARIADB_LSP_BIN."
