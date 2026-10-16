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

"""Static checks of the MariaDB CLI guard in the Pi extension.

``src/cli-guard.ts`` decides whether a shell command uses a MariaDB or MySQL
command-line client for what an MCP tool covers; ``src/index.ts`` blocks such a bash/powershell call and
adds the rule to the system prompt. The cases live in
``tests/cli-guard-cases.json`` at the repo root, shared with the other ports.
The module itself is byte-identical to the OpenCode plugin's
``lib/cli-guard.ts``; the OpenCode suite checks that.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from lib.skills import REPO_ROOT

pytestmark = pytest.mark.static

PLUGIN = REPO_ROOT / "pi" / "dev-plugin"
GUARD = PLUGIN / "src" / "cli-guard.ts"
CASES_FILE = REPO_ROOT / "tests" / "cli-guard-cases.json"

# Reads the cases, prints {"deny": [...missed...], "allow": [...wrongly denied...]}.
_RUNNER = """
import { readFileSync } from "node:fs";
const { findClient, guardDisabled } = await import(process.argv[1]);
const cases = JSON.parse(readFileSync(process.argv[2], "utf8"));
for (const api of cases.covered_shell_api) {
  const [object, method] = api.split(".");
  cases.deny.push(`mariadb-shell -- ${object} ${method.replaceAll("_", "-")} x`);
}
console.log(JSON.stringify({
  deny: cases.deny.filter((c) => !findClient(c)),
  allow: cases.allow.filter((c) => findClient(c)),
  off: guardDisabled({ MARIADB_PLUGIN_ALLOW_CLI: "1" }) && !guardDisabled({}),
}));
"""


def _node_strips_types() -> bool:
    node = shutil.which("node")
    if node is None:
        return False
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    major, minor = (int(part) for part in version.lstrip("v").split(".")[:2])
    return (major, minor) >= (22, 6)


@pytest.mark.skipif(not _node_strips_types(), reason="needs node 22.6+ to run TypeScript")
def test_guard_agrees_with_the_shared_cases():
    result = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", "--input-type=module",
         "-e", _RUNNER, GUARD.as_uri(), str(CASES_FILE)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    assert outcome == {"deny": [], "allow": [], "off": True}


def test_extension_wires_the_guard():
    """Blocks bash and powershell calls, adds the rule, honours the opt-out."""
    source = (PLUGIN / "src" / "index.ts").read_text()
    assert re.search(r'from "\./cli-guard\.ts"', source)
    assert 'pi.on("tool_call"' in source
    assert '"bash"' in source and '"powershell"' in source
    assert "block: true" in source
    assert 'pi.on("before_agent_start"' in source and "promptGuidelines" in source
    assert "guardDisabled()" in source
