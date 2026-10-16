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

"""Static checks of the MariaDB CLI guard hook (Claude Code and Codex).

The MCP-bearing plugins ship ``hooks/hooks.json`` + ``hooks/mariadb-cli-guard.sh``:
a PreToolUse hook on the shell tool that denies a command using a MariaDB or
MySQL command-line client for what an MCP tool covers, and lets everything else
run. Both harnesses read the same file format and expand
``${CLAUDE_PLUGIN_ROOT}``, so the copies are byte-identical across claude/ and
codex/. The cases live in ``tests/cli-guard-cases.json`` at the repo root and are
shared with the Pi, OpenCode and Hermes ports.

This module is identical in the claude and codex suites; it tests the plugins of
the harness it sits in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lib.skills import REPO_ROOT, TESTS_ROOT

pytestmark = pytest.mark.static

HARNESS_DIR = TESTS_ROOT.parent
CANONICAL = REPO_ROOT / "claude" / "dev-plugin" / "hooks"
CASES = json.loads((REPO_ROOT / "tests" / "cli-guard-cases.json").read_text())
# One `mariadb-shell -- <object> <method>` call per API an MCP tool covers.
CASES["deny"] += [
    f"mariadb-shell -- {api.split('.')[0]} {api.split('.')[1].replace('_', '-')} x"
    for api in CASES["covered_shell_api"]
]

# The plugins that carry the mariadb MCP server, and so the guard.
GUARDED = sorted(p for p in HARNESS_DIR.glob("*-plugin") if (p / ".mcp.json").is_file())

BASH = shutil.which("bash")


def _decision(hook: Path, command: str, env: dict | None = None) -> str:
    """Runs the hook on a shell-tool payload: 'deny' or 'allow'."""
    payload = json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "cwd": "/home/dev/git/mariadb-shell",
            "tool_input": {"command": command, "description": "x"},
        }
    )
    result = subprocess.run(
        [BASH, str(hook)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, **(env or {})},
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    if not result.stdout.strip():
        return "allow"
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "PreToolUse"
    assert "mariadb-shell -- mcp setup" in output["permissionDecisionReason"]
    return output["permissionDecision"]


def test_every_mcp_plugin_is_guarded():
    assert GUARDED, f"no plugin with an .mcp.json under {HARNESS_DIR}"


@pytest.mark.parametrize("plugin", GUARDED, ids=lambda p: p.name)
def test_hooks_json_runs_the_guard_on_the_shell_tool(plugin: Path):
    """Only description + hooks: Codex refuses any other top-level key."""
    config = json.loads((plugin / "hooks" / "hooks.json").read_text())
    assert set(config) == {"description", "hooks"}
    [entry] = config["hooks"]["PreToolUse"]
    assert entry["matcher"] == "Bash"
    [hook] = entry["hooks"]
    assert hook["type"] == "command"
    assert hook["command"] == '"${CLAUDE_PLUGIN_ROOT}/hooks/mariadb-cli-guard.sh"'


@pytest.mark.parametrize("plugin", GUARDED, ids=lambda p: p.name)
def test_hook_files_match_the_canonical_copy(plugin: Path):
    """Edit claude/dev-plugin/hooks/ and cp to the rest."""
    for name in ("hooks.json", "mariadb-cli-guard.sh"):
        assert (plugin / "hooks" / name).read_bytes() == (CANONICAL / name).read_bytes(), (
            f"{plugin.name}/hooks/{name} differs from claude/dev-plugin/hooks/{name}"
        )
    assert os.access(plugin / "hooks" / "mariadb-cli-guard.sh", os.X_OK)


@pytest.mark.skipif(BASH is None, reason="bash is not installed")
@pytest.mark.parametrize("command", CASES["deny"])
def test_guard_denies(command: str):
    assert _decision(CANONICAL / "mariadb-cli-guard.sh", command) == "deny"


@pytest.mark.skipif(BASH is None, reason="bash is not installed")
@pytest.mark.parametrize("command", CASES["allow"])
def test_guard_allows(command: str):
    assert _decision(CANONICAL / "mariadb-cli-guard.sh", command) == "allow"


@pytest.mark.skipif(BASH is None, reason="bash is not installed")
def test_guard_can_be_turned_off():
    hook = CANONICAL / "mariadb-cli-guard.sh"
    assert _decision(hook, "mariadb -e 1", {"MARIADB_PLUGIN_ALLOW_CLI": "1"}) == "allow"


@pytest.mark.skipif(BASH is None, reason="bash is not installed")
def test_guard_lets_a_payload_without_a_command_through():
    result = subprocess.run(
        [BASH, str(CANONICAL / "mariadb-cli-guard.sh")],
        input="not json",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (result.returncode, result.stdout) == (0, "")
