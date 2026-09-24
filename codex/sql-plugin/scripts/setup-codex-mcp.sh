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
# setup-codex-mcp.sh — register the mariadb-shell MCP server with Codex.
#
# This is a FALLBACK, not a required step. The plugin's own .mcp.json declares a
# working server: a relative command plus "cwd": "." (which Codex resolves to the
# plugin's install directory), naming the extensionless scripts/mariadb-mcp-launcher
# so that one command works on macOS, Linux and Windows alike. See that file for
# why. Use this script when that does not take effect — an older Codex, or a
# platform where the extensionless resolution does not hold.
#
# `codex mcp add` writes an ordinary [mcp_servers.mariadb] entry into
# $CODEX_HOME/config.toml with the absolute path resolved here, and it takes
# precedence over the plugin-provided entry of the same name.
#
# On Windows use setup-codex-mcp.cmd instead, and not merely because this needs
# bash: the entry below names the .sh launcher, which Codex — which spawns the
# command directly — cannot execute on a native Windows host. The .cmd script
# registers the .cmd launcher.
#
# Usage:
#   codex/dev-plugin/scripts/setup-codex-mcp.sh              # register (or update)
#   codex/dev-plugin/scripts/setup-codex-mcp.sh --remove     # unregister
#
# Environment:
#   CODEX_HOME              Codex config dir to write to (default ~/.codex).
#   CODEX_BIN               codex binary to use (default: the one on PATH).
#   MARIADB_SHELL_VERSION   Minimum mariadb-shell version to pass to the launcher.

set -euo pipefail

SERVER_NAME="mariadb"
SHELL_VERSION="26.9.4"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHER="$PLUGIN_ROOT/scripts/mariadb-mcp-launcher.sh"

CODEX="${CODEX_BIN:-$(command -v codex || true)}"
[ -n "$CODEX" ] || { echo "error: codex not found (set CODEX_BIN or add it to PATH)" >&2; exit 1; }
[ -x "$LAUNCHER" ] || { echo "error: launcher not executable: $LAUNCHER" >&2; exit 1; }

if [ "${1:-}" = "--remove" ]; then
  "$CODEX" mcp remove "$SERVER_NAME"
  exit 0
fi

# Re-registering the same name is how an update is done, so drop any existing
# entry first rather than letting `add` fail on the collision.
"$CODEX" mcp remove "$SERVER_NAME" >/dev/null 2>&1 || true

"$CODEX" mcp add "$SERVER_NAME" \
  --env "MARIADB_SHELL_VERSION=$SHELL_VERSION" \
  -- "$LAUNCHER"

echo "Registered MCP server '$SERVER_NAME' -> $LAUNCHER"
echo "Verify with: $CODEX mcp get $SERVER_NAME"
