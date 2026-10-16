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

"""Static checks of the MariaDB CLI guard plugin for Hermes Agent.

``hermes/guard-plugin`` is a Python plugin of its own (Hermes runs hooks only
from one, and a folder with a plugin.yaml is never read as a portable package).
Its ``pre_tool_call`` hook blocks a ``terminal`` call using a MariaDB or MySQL
command-line client for what an MCP tool covers, and lets everything else run. The cases live in ``tests/cli-guard-cases.json`` at the
repo root, shared with the other ports.
"""

from __future__ import annotations

import importlib.util
import json

import pytest

from lib.skills import REPO_ROOT

pytestmark = pytest.mark.static

GUARD_DIR = REPO_ROOT / "hermes" / "guard-plugin"
CASES = json.loads((REPO_ROOT / "tests" / "cli-guard-cases.json").read_text())
# One `mariadb-shell -- <object> <method>` call per API an MCP tool covers.
CASES["deny"] += [
    f"mariadb-shell -- {api.split('.')[0]} {api.split('.')[1].replace('_', '-')} x"
    for api in CASES["covered_shell_api"]
]


def _load_guard():
    spec = importlib.util.spec_from_file_location("mariadb_guard", GUARD_DIR / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


@pytest.mark.parametrize("command", CASES["deny"])
def test_guard_denies(command: str):
    result = guard._pre_tool_call(tool_name="terminal", args={"command": command})
    assert result is not None and result["action"] == "block"
    assert "mariadb-shell -- mcp setup" in result["message"]


@pytest.mark.parametrize("command", CASES["allow"])
def test_guard_allows(command: str):
    assert guard._pre_tool_call(tool_name="terminal", args={"command": command}) is None


def test_guard_looks_only_at_the_terminal_tool():
    assert guard._pre_tool_call(tool_name="read_file", args={"path": "mariadb -e 1"}) is None
    assert guard._pre_tool_call(tool_name="terminal", args={"command": None}) is None
    assert guard._pre_tool_call(tool_name="terminal", args="mariadb -e 1") is None


class _Context:
    def __init__(self):
        self.hooks, self.sections = [], []

    def register_hook(self, name, callback):
        self.hooks.append(name)

    def register_system_prompt_section(self, section_id, content):
        self.sections.append(section_id)


def test_register_adds_the_hook_and_the_prompt_section(monkeypatch):
    monkeypatch.delenv("MARIADB_PLUGIN_ALLOW_CLI", raising=False)
    ctx = _Context()
    guard.register(ctx)
    assert ctx.hooks == ["pre_tool_call"]
    assert ctx.sections == ["mariadb-guard.db-access"]


def test_guard_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("MARIADB_PLUGIN_ALLOW_CLI", "1")
    ctx = _Context()
    guard.register(ctx)
    assert ctx.hooks == ctx.sections == []


def test_manifest_declares_a_python_plugin():
    manifest = (GUARD_DIR / "plugin.yaml").read_text()
    assert "name: mariadb-guard" in manifest
    assert "pre_tool_call" in manifest
    # A plugin.json beside it would never be read: plugin.yaml wins.
    assert not (GUARD_DIR / "plugin.json").exists()


def test_install_scanner_word_stays_out_of_prose():
    """Hermes' install scan rates the word for running as root HIGH in prose.

    Only the wrapper list may carry it, as a quoted string; a comment or
    docstring with it made the install need --force.
    """
    word = "su" + "do"
    for line in (GUARD_DIR / "__init__.py").read_text().splitlines():
        if word in line:
            assert f'"{word}"' in line and not line.lstrip().startswith("#")
