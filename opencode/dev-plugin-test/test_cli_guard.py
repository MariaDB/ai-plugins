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

"""Static checks of the MariaDB CLI guard plugin for OpenCode.

Each MCP-bearing plugin lists ``plugins/mariadb-guard.ts`` in its opencode.json;
that plugin throws on a bash call using a MariaDB or MySQL command-line client
for what an MCP tool covers,
and adds the rule to the system prompt. Its detection, ``lib/cli-guard.ts``, is
byte-identical to the Pi extension's ``src/cli-guard.ts``, which the Pi suite
runs against the shared cases.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.skills import REPO_ROOT, TESTS_ROOT

pytestmark = pytest.mark.static

HARNESS_DIR = TESTS_ROOT.parent
CANONICAL = REPO_ROOT / "pi" / "dev-plugin" / "src" / "cli-guard.ts"

# The plugins that carry the mariadb MCP server, and so the guard.
GUARDED = sorted(
    p.parent for p in HARNESS_DIR.glob("*-plugin/opencode.json")
    if "mcp" in json.loads(p.read_text())
)


def test_every_mcp_plugin_is_guarded():
    assert GUARDED, f"no plugin with an mcp block under {HARNESS_DIR}"


@pytest.mark.parametrize("plugin", GUARDED, ids=lambda p: p.name)
def test_opencode_json_loads_the_guard(plugin: Path):
    """Through the plugin's own env var, so the entry survives a merge."""
    config = json.loads((plugin / "opencode.json").read_text())
    [launcher] = config["mcp"]["mariadb"]["command"]
    root_var = launcher.split("}")[0] + "}"
    assert root_var.startswith("{env:")
    assert config["plugin"] == [f"{root_var}/plugins/mariadb-guard.ts"]


@pytest.mark.parametrize("plugin", GUARDED, ids=lambda p: p.name)
def test_guard_module_matches_the_pi_extension(plugin: Path):
    assert (plugin / "lib" / "cli-guard.ts").read_bytes() == CANONICAL.read_bytes(), (
        f"{plugin.name}/lib/cli-guard.ts differs from pi/dev-plugin/src/cli-guard.ts"
    )


@pytest.mark.parametrize("plugin", GUARDED, ids=lambda p: p.name)
def test_plugin_wires_the_guard(plugin: Path):
    plugins = sorted(p.name for p in (plugin / "plugins").iterdir())
    # OpenCode would also load anything else in a plugins/ dir it scans.
    assert plugins == ["mariadb-guard.ts"]
    source = (plugin / "plugins" / "mariadb-guard.ts").read_text()
    assert 'from "../lib/cli-guard.ts"' in source
    assert '"tool.execute.before"' in source and "throw new Error" in source
    assert 'input.tool !== "bash"' in source
    assert '"experimental.chat.system.transform"' in source
    assert "guardDisabled()" in source
