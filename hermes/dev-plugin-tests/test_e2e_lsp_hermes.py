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

"""Tier 4 — the SQL language server end to end via the real Hermes CLI.

Opt-in (`pytest -m e2e`). A Hermes plugin cannot register a language server, so
the README has users add an `lsp.servers` entry to their config.yaml; this test
adds exactly that entry (and the `warmup_timeout` it recommends) to a temporary
profile with the working tree's plugin installed, and starts from a **clean
install**:

  * the plugin's mcp.json gets an empty MARIADB_SHELL_BINDIR / PREFIX. Hermes
    passes an MCP server only its configured env plus PATH, HOME and a few
    others, so this is the only way to keep the MCP launcher off ~/.local;
  * the `lsp.servers` entry gets the same two variables;
  * hermes runs with a PATH stripped of every directory holding a
    `mariadb-shell` or `mariadb-lsp`.

Hermes connects MCP servers at session start, so the MCP launcher downloads the
package, while the language server is spawned on the first `.sql` write and has
to wait for that install, within Hermes' warm-up budget.

  1. the run finished;
  2. exactly one package landed in the clean prefix, with `mariadb-lsp` linked
     into the clean bin dir → one download, by the MCP launcher;
  3. the `write_file` of a `.sql` file with a syntax error came back with
     `lsp_diagnostics` from mariadb-lsp.

Knobs (all optional): HERMES_BIN, HERMES_HOME, E2E_TIMEOUT.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import hermes_cli

pytestmark = pytest.mark.e2e

TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "900"))
# The README's recommendation: room for a first start's download.
WARMUP_TIMEOUT = 240

BROKEN_SQL = "broken.sql"
# A doubled comma: a syntax error any MariaDB parser reports.
BROKEN = "CREATE TABLE note (id INT PRIMARY KEY,, title VARCHAR(200));\n"


def _clean_path() -> str:
    """PATH without any directory that would hand the launchers a binary."""
    keep = [
        d for d in os.environ.get("PATH", "").split(os.pathsep)
        if d and not any((Path(d) / n).exists() for n in ("mariadb-shell", "mariadb-lsp"))
    ]
    return os.pathsep.join(keep)


def _add_lsp_server(profile: hermes_cli.TemporaryProfile, clean_env: dict) -> None:
    """The README's `lsp` entry, pointing at the plugin installed in this profile."""
    import yaml

    config_path = profile.home / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    lsp = config.setdefault("lsp", {})
    lsp["enabled"] = True
    lsp["warmup_timeout"] = WARMUP_TIMEOUT
    launcher = profile.installed_plugin_dir() / "scripts" / "mariadb-lsp-launcher.sh"
    # Written as the README writes it, from ~: Hermes expands the tilde itself.
    home = Path.home()
    command = f"~/{launcher.relative_to(home).as_posix()}" if launcher.is_relative_to(home) else str(launcher)
    lsp.setdefault("servers", {})["mariadb"] = {
        "command": [command],
        "extensions": [".sql"],
        "language_id": "sql",
        "env": {"MARIADB_SHELL_VERSION": _shell_version(), **clean_env},
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")


def _shell_version() -> str:
    mcp = json.loads((hermes_cli.PLUGIN_ROOT / "mcp.json").read_text(encoding="utf-8"))
    return mcp["mcpServers"][hermes_cli.SERVER_NAME]["env"]["MARIADB_SHELL_VERSION"]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    reason = hermes_cli.missing_prerequisite()
    if reason:
        pytest.skip(reason)

    root = tmp_path_factory.mktemp("hermes_lsp_clean")
    bindir, prefix, project = root / "bin", root / "share", root / "project"
    for d in (bindir, prefix, project):
        d.mkdir()
    # Hermes runs language servers in git repositories only.
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    clean_env = {"MARIADB_SHELL_BINDIR": str(bindir), "MARIADB_SHELL_PREFIX": str(prefix)}

    with hermes_cli.TemporaryProfile() as profile:
        installed = profile.install_plugin(tmp_path_factory.mktemp("hermes_lsp_src"), mcp_env=clean_env)
        assert installed.returncode == 0, (
            f"hermes plugins install failed (exit {installed.returncode}):\n"
            f"{installed.stdout[-3000:]}\n{installed.stderr[-2000:]}"
        )
        reason = hermes_cli.provider_ready(profile, tmp_path_factory.mktemp("hermes_lsp_ready"))
        if reason:
            pytest.skip(reason)
        _add_lsp_server(profile, clean_env)

        env = dict(os.environ)
        env.update({"PATH": _clean_path(), **clean_env})
        for key in ("MARIADB_SHELL_BIN", "MARIADB_LSP_BIN"):
            env.pop(key, None)
        prompt = (
            f"Use the write_file tool to write the file {BROKEN_SQL} in the current "
            f"directory with exactly this content:\n{BROKEN}\n"
            "Do not fix it and write it only once. Then reply with the lsp_diagnostics "
            "the write_file result reported, verbatim, or say that there were none."
        )
        result = hermes_cli.run_hermes(profile, prompt, project=project, timeout=TIMEOUT,
                                       max_turns=6, env=env)
        print(f"hermes LSP e2e ran against model: {result.model()}")
        yield {"run": result, "bindir": bindir, "prefix": prefix}


def test_step1_run_finished(run):
    result = run["run"]
    assert not result.timed_out, f"hermes did not finish within {TIMEOUT}s.{result.diagnostics}"
    assert result.returncode == 0, f"hermes exited {result.returncode}.{result.diagnostics}"


def test_step2_one_install_by_the_mcp_launcher(run):
    packages = sorted(p.name for p in run["prefix"].iterdir() if p.is_dir())
    assert len(packages) == 1, (
        f"expected one installed package in the clean prefix, got {packages}.{run['run'].diagnostics}"
    )
    assert (run["bindir"] / "mariadb-lsp").exists(), (
        f"the installed package linked no mariadb-lsp into {run['bindir']}"
    )


def test_step3_write_file_reported_mariadb_diagnostics(run):
    result = run["run"]
    writes = result.tool_results("write_file")
    assert writes, f"the model never called write_file.{result.diagnostics}"
    raw = "\n".join(json.dumps(e) for e in writes)
    assert "lsp_diagnostics" in raw, (
        f"no write_file result carried lsp_diagnostics, so mariadb-lsp did not answer "
        f"within Hermes' budget:\n{raw[:2000]}{result.diagnostics}"
    )
    assert "mariadb" in raw.lower() and ("syntax" in raw.lower() or "ERROR" in raw), (
        f"the lsp_diagnostics are not mariadb-lsp's syntax error:\n{raw[:2000]}"
    )
