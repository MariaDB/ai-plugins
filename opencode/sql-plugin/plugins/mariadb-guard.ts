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

// MariaDB CLI guard for OpenCode, loaded through the `plugin` entry of this
// plugin's opencode.json.
//
// Keeps the agent from using the MariaDB/MySQL command-line clients for what
// the mariadb MCP server's tools do (see ../lib/cli-guard.ts): the system prompt
// says to use the tools, and a bash call that uses a client for such a task is
// blocked - the thrown Error's message, which names the tool to call instead, is
// what the model gets as the tool result. Starting OpenCode with
// MARIADB_PLUGIN_ALLOW_CLI=1 turns both off.

import { SYSTEM_PROMPT_RULE, blockReason, findClient, guardDisabled } from "../lib/cli-guard.ts";

export const MariadbCliGuard = async () => {
  if (guardDisabled()) return {};

  return {
    "tool.execute.before": async (
      input: { tool: string },
      output: { args?: { command?: unknown } },
    ) => {
      if (input.tool !== "bash") return;
      const command = output.args?.command;
      if (typeof command !== "string") return;
      const finding = findClient(command);
      if (finding) throw new Error(blockReason(finding));
    },
    "experimental.chat.system.transform": async (
      _input: unknown,
      output: { system: string[] },
    ) => {
      output.system.push(SYSTEM_PROMPT_RULE);
    },
  };
};
