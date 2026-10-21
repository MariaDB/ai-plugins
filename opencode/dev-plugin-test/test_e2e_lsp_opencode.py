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

"""Tier 4 — the SQL language server end to end via the real OpenCode CLI.

Opt-in (`pytest -m e2e`). OpenCode reads the plugin's `opencode.json` as its
config (OPENCODE_CONFIG), so the `lsp` block is exercised as users merge it,
and every run starts from a **clean install**: an empty MARIADB_SHELL_BINDIR /
MARIADB_SHELL_PREFIX and a PATH with every directory holding a
`mariadb-shell` or `mariadb-lsp` removed.

Without a model (always runs when `opencode` is present):

  1. the MCP launcher, run once as OpenCode would run it, installs exactly one
     package, with `mariadb-lsp` linked into the clean bin dir;
  2. `opencode debug lsp diagnostics` on a `.sql` file with a syntax error
     starts the plugin's language server through the LSP launcher and returns
     mariadb-lsp's `syntax-error` diagnostic.

With a model (skips unless OpenCode can answer a trivial prompt; pick one with
E2E_OPENCODE_MODEL, as provider/model):

  3. one `opencode run`, from a second clean install: OpenCode starts the MCP
     server at session start (which downloads the package) and the language
     server on the model's first `.sql` write (which waits for that download);
     the write tool's result carries mariadb-lsp's syntax error, and one
     package was installed.

OpenCode gives a language server 45 s to initialize and then skips it for the
rest of the session, so step 3 only passes when the download beats that.

Knobs (all optional): OPENCODE_BIN, E2E_OPENCODE_MODEL, E2E_TIMEOUT.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

PLUGIN_DIR = Path(__file__).resolve().parent.parent / "dev-plugin"
# Resolved as OpenCode resolves the plugin's command: the extensionless
# wrapper on macOS and Linux, through %PATHEXT% to the .cmd on Windows.
MCP_LAUNCHER = shutil.which("mariadb-mcp-launcher", path=str(PLUGIN_DIR / "scripts"))
# Windows installs .cmd shims (install.ps1), elsewhere the names are links.
SUFFIXES = (".cmd", ".exe", "") if os.name == "nt" else ("",)
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "900"))
MODEL = os.environ.get("E2E_OPENCODE_MODEL", "")

BROKEN_SQL = "broken.sql"
# A doubled comma: a syntax error any MariaDB parser reports.
BROKEN = "CREATE TABLE note (id INT PRIMARY KEY,, title VARCHAR(200));\n"


def _opencode_bin() -> str:
    found = os.environ.get("OPENCODE_BIN") or shutil.which("opencode") or ""
    return str(Path(found).resolve()) if found else ""


def _clean_path() -> str:
    """PATH without any directory that would hand the launchers a binary."""
    keep = [
        d for d in os.environ.get("PATH", "").split(os.pathsep)
        if d and not any((Path(d) / (n + x)).exists()
                         for n in ("mariadb-shell", "mariadb-lsp") for x in SUFFIXES)
    ]
    return os.pathsep.join(keep)


def _clean_setup(root: Path) -> dict:
    """Empty install dirs, a git project with the broken file, and the env."""
    bindir, prefix, project = root / "bin", root / "share", root / "project"
    for d in (bindir, prefix, project):
        d.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)

    # The plugin's opencode.json, plus edit permission for the model run.
    config = json.loads((PLUGIN_DIR / "opencode.json").read_text(encoding="utf-8"))
    config["permission"] = {"edit": "allow"}
    config_path = root / "opencode.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    env = dict(os.environ)
    env.update({
        "PATH": _clean_path(),
        "MARIADB_SHELL_BINDIR": str(bindir),
        "MARIADB_SHELL_PREFIX": str(prefix),
        # OpenCode pastes {env:...} into the JSON text before parsing it, so a
        # Windows path needs forward slashes to stay valid JSON.
        "MARIADB_DEV_PLUGIN": PLUGIN_DIR.as_posix(),
        "OPENCODE_CONFIG": str(config_path),
    })
    for key in ("MARIADB_SHELL_BIN", "MARIADB_LSP_BIN"):
        env.pop(key, None)
    return {"bindir": bindir, "prefix": prefix, "project": project, "env": env}


def _packages(prefix: Path) -> list:
    return sorted(p.name for p in prefix.iterdir() if p.is_dir())


@pytest.fixture(scope="module")
def opencode():
    found = _opencode_bin()
    if not found:
        pytest.skip("opencode CLI not found (set OPENCODE_BIN or add it to PATH)")
    return found


@pytest.fixture(scope="module")
def installed(tmp_path_factory, opencode):
    """A clean install made by the MCP launcher, as OpenCode would start it."""
    setup = _clean_setup(tmp_path_factory.mktemp("opencode_lsp_clean"))
    assert MCP_LAUNCHER, f"no mariadb-mcp-launcher in {PLUGIN_DIR / 'scripts'}"
    # stdin at EOF: once installed, the shell's MCP server starts and ends.
    run = subprocess.run([MCP_LAUNCHER], env=setup["env"], stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=TIMEOUT)
    setup["launcher"] = run
    return setup


def test_step1_mcp_launcher_installs_once(installed):
    packages = _packages(installed["prefix"])
    assert len(packages) == 1, (
        f"expected one installed package, got {packages}:\n{installed['launcher'].stderr[-2000:]}"
    )
    assert any((installed["bindir"] / ("mariadb-lsp" + x)).exists() for x in SUFFIXES), (
        f"the package linked no mariadb-lsp into {installed['bindir']}"
    )


def test_step2_opencode_reports_mariadb_diagnostics(installed, opencode):
    project = installed["project"]
    (project / BROKEN_SQL).write_text(BROKEN, encoding="utf-8")
    run = subprocess.run([opencode, "debug", "lsp", "diagnostics", BROKEN_SQL],
                         cwd=project, env=installed["env"], stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, f"opencode exited {run.returncode}:\n{run.stderr[-2000:]}"
    start = run.stdout.find("{")
    diagnostics = json.loads(run.stdout[start:]) if start >= 0 else {}
    found = [d for ds in diagnostics.values() for d in ds]
    mariadb = [d for d in found if d.get("source") == "mariadb" and d.get("code") == "syntax-error"]
    assert mariadb, (
        "OpenCode returned no mariadb-lsp syntax error for the broken file, so the "
        f"plugin's lsp block did not start the server:\n{run.stdout[-2000:]}\n{run.stderr[-2000:]}"
    )
    assert mariadb[0]["range"]["start"] == {"line": 0, "character": 38}


def _opencode_run(opencode: str, prompt: str, cwd: Path, env=None, timeout=300):
    """One `opencode run --format json`; returns the process and its JSON events."""
    model = ["-m", MODEL] if MODEL else []
    run = subprocess.run([opencode, "run", *model, "--format", "json", prompt],
                         cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                         capture_output=True, text=True, timeout=timeout)
    events = []
    for line in run.stdout.splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return run, events


@pytest.fixture(scope="module")
def model_run(tmp_path_factory, opencode):
    """One model-driven run from a clean install; skips without a model."""
    probe, _ = _opencode_run(opencode, "Reply with exactly: READY", tmp_path_factory.mktemp("opencode_probe"))
    if "READY" not in probe.stdout:
        errors = [ln for ln in probe.stdout.splitlines() if '"type":"error"' in ln.replace(" ", "")]
        pytest.skip(f"OpenCode cannot reach a model (set E2E_OPENCODE_MODEL, or log in with "
                    f"`opencode auth login`): {(errors or [probe.stderr])[-1][:300]}")

    setup = _clean_setup(tmp_path_factory.mktemp("opencode_lsp_model"))
    # One line: on Windows, `opencode` is an npm .cmd wrapper, and a batch file
    # cuts an argument at its first line break.
    prompt = (
        f"Use your write tool to create the file {BROKEN_SQL} in the current directory "
        f"whose content is exactly this one line: {BROKEN.strip()} "
        "Do not fix it and write it only once. Then reply with any diagnostics the "
        "write reported, verbatim, or say that there were none."
    )
    run, events = _opencode_run(opencode, prompt, setup["project"], setup["env"], TIMEOUT)
    setup.update(run=run, events=events)
    return setup


def test_step3_write_reports_diagnostics_after_a_clean_install(model_run):
    run, events = model_run["run"], model_run["events"]
    assert run.returncode == 0, f"opencode run exited {run.returncode}:\n{run.stderr[-2000:]}"
    tools = [e["part"] for e in events if (e.get("part") or {}).get("type") == "tool"]
    writes = [t for t in tools if BROKEN_SQL in json.dumps(t.get("state", {}).get("input", {}))]
    assert writes, f"the model never wrote {BROKEN_SQL}; tools used: {[t.get('tool') for t in tools]}"
    output = "\n".join(str(t.get("state", {}).get("output", "")) for t in writes)
    assert "syntax error near ','" in output, (
        "the write tool's result carried no mariadb-lsp diagnostic, so OpenCode's language "
        f"server did not answer within its 45 s initialize budget:\n{output[-2000:]}"
    )
    assert len(_packages(model_run["prefix"])) == 1, "more than one package was installed"
