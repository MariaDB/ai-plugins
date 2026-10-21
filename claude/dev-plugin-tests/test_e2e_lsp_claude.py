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

"""Tier 4 — the SQL language server end to end via the real Claude Code CLI.

Opt-in (`pytest -m e2e`). One `claude -p` run loads the working tree's plugin
with `--plugin-dir`, so Claude Code reads its `.lsp.json` and `.mcp.json` the
way it does for an installed plugin, and starts from a **clean install**: an
empty MARIADB_SHELL_BINDIR / MARIADB_SHELL_PREFIX and a PATH with every
directory holding a `mariadb-shell` or `mariadb-lsp` removed. So:

  * the MCP launcher, started at session start, downloads the package;
  * the LSP launcher, started when the model first touches a `.sql` file, finds
    no shell yet and waits for that install instead of running one of its own;
  * Claude Code must not give up on the language server meanwhile
    (`startupTimeout` in `.lsp.json`).

The steps, each its own test over the one run:

  1. the run finished and wrote `schema.sql`;
  2. exactly one package landed in the clean prefix, with `mariadb-lsp` linked
     into the clean bin dir → one download, by the MCP launcher;
  3. Claude Code's debug log shows the `plugin:<name>:mariadb` language server
     initialized, and no LSP start failure or timeout;
  4. an `LSP` tool call answered with the tables `schema.sql` defines → the
     server Claude talked to is mariadb-lsp, over the plugin's launcher.

The LSP tool is gated behind ENABLE_LSP_TOOL, which the run sets. Only `Write`
and `LSP` are allowed; no permission bypass is needed.

Knobs (all optional): CLAUDE_BIN, E2E_MODEL, E2E_TIMEOUT.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "dev-plugin"
PLUGIN_NAME = json.loads((PLUGIN_DIR / ".claude-plugin" / "plugin.json").read_text())["name"]
LSP_SERVER = f"plugin:{PLUGIN_NAME}:mariadb"

MODEL = os.environ.get("E2E_MODEL", "claude-opus-4-8")
# A first start downloads mariadb-shell before either server answers.
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "900"))

SCHEMA_SQL = "schema.sql"
SCHEMA = (
    "CREATE TABLE notebook (id INT PRIMARY KEY, name VARCHAR(100));\n"
    "CREATE TABLE note (id INT PRIMARY KEY, notebook_id INT, title VARCHAR(200));\n"
)
TABLES = ("notebook", "note")


def _claude_bin() -> str:
    return os.environ.get("CLAUDE_BIN") or shutil.which("claude") or ""


# Windows installs .cmd shims (install.ps1), elsewhere the names are links.
SUFFIXES = (".cmd", ".exe", "") if os.name == "nt" else ("",)


def _clean_path() -> str:
    """PATH without any directory that would hand the launchers a binary."""
    keep = [
        d for d in os.environ.get("PATH", "").split(os.pathsep)
        if d and not any((Path(d) / (n + x)).exists()
                         for n in ("mariadb-shell", "mariadb-lsp") for x in SUFFIXES)
    ]
    return os.pathsep.join(keep)


PROMPT = (
    f"Write the file {SCHEMA_SQL} in the current directory containing exactly:\n"
    f"{SCHEMA}\n"
    f"Then use the LSP tool with the documentSymbol operation on {SCHEMA_SQL}. "
    "The language server may still be starting: if the call says so, call it "
    "again (up to ten times: on a first start it waits for the shell download). "
    "Reply with the symbol names it returned, or quote "
    "the last error if it never succeeded."
)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    claude = _claude_bin()
    if not claude:
        pytest.skip("claude CLI not found (set CLAUDE_BIN or add it to PATH)")
    claude = str(Path(claude).resolve())  # PATH is narrowed below

    root = tmp_path_factory.mktemp("lsp_clean")
    bindir, prefix, project = root / "bin", root / "share", root / "project"
    for d in (bindir, prefix, project):
        d.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    debug_log = root / "claude-debug.log"

    env = dict(os.environ)
    env.update({
        "PATH": _clean_path(),
        "MARIADB_SHELL_BINDIR": str(bindir),
        "MARIADB_SHELL_PREFIX": str(prefix),
        "ENABLE_LSP_TOOL": "1",
    })
    for key in ("MARIADB_SHELL_BIN", "MARIADB_LSP_BIN"):
        env.pop(key, None)

    cmd = [
        claude, "-p", PROMPT,
        "--model", MODEL,
        "--plugin-dir", str(PLUGIN_DIR),
        "--allowedTools", "Write,LSP",
        "--output-format", "stream-json", "--verbose",
        "--debug-file", str(debug_log),
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=project, env=env, capture_output=True, text=True,
                              timeout=TIMEOUT, stdin=subprocess.DEVNULL)
        returncode, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
    except subprocess.TimeoutExpired as exc:
        returncode, timed_out = -1, True
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
    elapsed = time.monotonic() - started

    events = []
    for line in stdout.splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    log = debug_log.read_text(encoding="utf-8", errors="replace") if debug_log.exists() else ""
    print(f"claude run took {elapsed:.0f}s")
    yield {
        "returncode": returncode, "timed_out": timed_out, "stderr": stderr,
        "events": events, "log": log, "project": project, "bindir": bindir, "prefix": prefix,
    }


def _diagnostics(run: dict) -> str:
    result = next((e.get("result") for e in reversed(run["events"]) if e.get("type") == "result"), "")
    lsp_log = "\n".join(ln for ln in run["log"].splitlines() if "LSP" in ln)[-4000:]
    return (
        f"\n--- LSP lines of the debug log ---\n{lsp_log}"
        f"\n--- claude stderr ---\n{run['stderr'][-1500:]}"
        f"\n--- final reply ---\n{str(result)[-1500:]}"
    )


def _tool_results(run: dict, tool: str) -> list[dict]:
    """tool_result blocks answering the tool_use blocks of `tool`."""
    ids, results = set(), []
    for event in run["events"]:
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use" and block.get("name") == tool:
                ids.add(block.get("id"))
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in ids:
                results.append(block)
    return results


def _text(block: dict) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return "\n".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
    return str(content or "")


def test_step1_run_finished_and_wrote_the_file(run):
    assert not run["timed_out"], f"claude did not finish within {TIMEOUT}s.{_diagnostics(run)}"
    assert run["returncode"] == 0, f"claude exited {run['returncode']}.{_diagnostics(run)}"
    assert (run["project"] / SCHEMA_SQL).is_file(), f"{SCHEMA_SQL} was not written.{_diagnostics(run)}"


def test_step2_one_install_by_the_mcp_launcher(run):
    packages = sorted(p.name for p in run["prefix"].iterdir() if p.is_dir())
    assert len(packages) == 1, f"expected one installed package in the clean prefix, got {packages}"
    assert any((run["bindir"] / ("mariadb-lsp" + x)).exists() for x in SUFFIXES), (
        f"the installed package linked no mariadb-lsp into {run['bindir']}: "
        f"{sorted(p.name for p in run['bindir'].iterdir())}"
    )
    installs = run["log"].count("mariadb-mcp-launcher: no suitable mariadb-shell found; installing")
    assert installs <= 1, f"the MCP launcher installed {installs} times"
    if "mariadb-lsp-launcher: no mariadb-shell" in run["log"]:
        print("the LSP launcher waited for the MCP launcher's install")


def test_step3_language_server_started_in_time(run):
    log = run["log"]
    assert f"LSP server {LSP_SERVER} initialized" in log, (
        f"Claude Code never initialized {LSP_SERVER}.{_diagnostics(run)}"
    )
    # The MCP server has the same name, so only LSP lines count.
    failures = [
        ln for ln in log.splitlines()
        if LSP_SERVER in ln and "LSP" in ln and "MCP server" not in ln
        and re.search(r"(?i)timed? ?out|failed to start|crash", ln)
    ]
    assert not failures, "LSP start failures:\n" + "\n".join(failures[:10])
    took = re.search(rf"\[LSP PROTOCOL {re.escape(LSP_SERVER)}\] Received response 'initialize - \(0\)' in (\d+)ms", log)
    if took:
        print(f"mariadb-lsp answered initialize after {int(took.group(1)) / 1000:.1f}s")


def test_step4_lsp_tool_returned_the_tables(run):
    results = _tool_results(run, "LSP")
    assert results, f"the model made no LSP tool call.{_diagnostics(run)}"
    good = [r for r in results if not r.get("is_error") and all(t in _text(r) for t in TABLES)]
    assert good, (
        f"no LSP tool result listed the tables {TABLES}:\n"
        + "\n---\n".join(_text(r)[:800] for r in results) + _diagnostics(run)
    )
