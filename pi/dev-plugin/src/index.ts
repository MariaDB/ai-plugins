// Copyright (c) 2026, MariaDB plc.
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License, version 2.0,
// as published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
// the GNU General Public License, version 2.0, for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software Foundation, Inc.,
// 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

// MariaDB dev extension for the Pi coding agent (pi.dev), Pi 1.0 or later.
//
// Two moving parts make up this plugin:
//   1. Skills — vendored under ./skills and declared via the package.json `pi`
//      field, so pi loads them contextually. This extension does not touch them.
//   2. The native mariadb-shell MCP server — registered here with Pi's built-in
//      MCP support (`pi.registerMcpServer`), so installing the package is all it
//      takes. The launcher script finds or installs a suitable mariadb-shell.
//
// Registrations are per session and not written to any mcp.json, so `pi mcp list`
// (which loads no extensions) does not show the server; `/mcp` inside pi does. A
// `mariadb` entry in ~/.pi/agent/mcp.json or .pi/mcp.json takes precedence over
// this one, which is how a user overrides the command or its environment.

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const MCP_SERVER_NAME = "mariadb";

// Plugin root = one level up from src/. Resolved from import.meta.url so it is
// correct wherever pi installs the package.
const PLUGIN_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const LAUNCHER = join(
  PLUGIN_ROOT,
  "scripts",
  process.platform === "win32" ? "mariadb-mcp-launcher.cmd" : "mariadb-mcp-launcher.sh",
);

export default function (pi: ExtensionAPI) {
  pi.registerMcpServer(MCP_SERVER_NAME, {
    command: LAUNCHER,
    args: [],
    description:
      "MariaDB Shell: connect to MariaDB servers, run SQL, inspect schemas, " +
      "manage sandbox instances, versioned schemas (MSM) and MySQL migrations",
  });
}
