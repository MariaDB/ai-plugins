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
# setup-pi-mcp.sh — register the mariadb-shell MCP server with pi-mcp-adapter.
#
# pi-mcp-adapter (npm:pi-mcp-adapter) is what connects the Pi coding agent to MCP
# servers: it reads a server list from an mcp.json config and exposes them through
# a single `mcp` proxy tool. This plugin ships the native mariadb-shell MCP server
# (started by scripts/mariadb-mcp-launcher.sh); this script adds/updates an entry
# for it in the adapter's config so pi can reach MariaDB.
#
# Target config (pi-mcp-adapter reads these; we write one of them):
#   default / --global : ${XDG_CONFIG_HOME:-~/.config}/mcp/mcp.json  (all projects)
#   --project          : ./.mcp.json in the current directory
#   --config PATH      : an explicit file
#
# Idempotent: re-running updates the "mariadb" entry in place and leaves any other
# servers and adapter settings in the file untouched.
#
# Requires: jq. On Windows run it from Git Bash / WSL (the launcher it points at is
# the .sh; native cmd.exe users should instead point at mariadb-mcp-launcher.cmd).

set -euo pipefail

SERVER_NAME="mariadb"
SHELL_VERSION="26.9.4"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHER="$PLUGIN_ROOT/scripts/mariadb-mcp-launcher.sh"

command -v jq >/dev/null 2>&1 || { echo "error: jq is required" >&2; exit 1; }

CONFIG=""
SCOPE="global"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) SCOPE="project"; shift ;;
    --global)  SCOPE="global";  shift ;;
    --config)  CONFIG="${2:-}"; shift 2 ;;
    -h|--help)
      echo "usage: setup-pi-mcp.sh [--global | --project | --config PATH]"; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [ -z "$CONFIG" ]; then
  if [ "$SCOPE" = "project" ]; then
    CONFIG="$(pwd)/.mcp.json"
  else
    CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/mcp/mcp.json"
  fi
fi

mkdir -p "$(dirname "$CONFIG")"
[ -f "$CONFIG" ] || echo '{}' > "$CONFIG"

# Merge the mariadb server entry, preserving every other key. lifecycle "lazy"
# lets the adapter spawn mariadb-shell only when a MariaDB tool is first used.
tmp="$(mktemp)"
jq \
  --arg name "$SERVER_NAME" \
  --arg cmd "$LAUNCHER" \
  --arg ver "$SHELL_VERSION" \
  '.mcpServers = ((.mcpServers // {}) + {
      ($name): {
        command: $cmd,
        args: [],
        env: { "MARIADB_SHELL_VERSION": $ver },
        lifecycle: "lazy"
      }
   })' "$CONFIG" > "$tmp"
mv "$tmp" "$CONFIG"

echo "Registered MCP server '$SERVER_NAME' -> $LAUNCHER in $CONFIG"
