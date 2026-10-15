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

"""Tier 4 — end-to-end via the real Codex CLI (opt-in: `pytest -m e2e`).

The Codex counterpart of `claude/dev-plugin-tests/test_e2e_claude.py`: it drives
the actual `codex` binary with this plugin installed and its mariadb-shell MCP
server wired in, then proves the whole stack worked by its side effects. The one
expensive `codex exec` happens in the module-scoped `workflow` fixture; every
side effect below is a separate `test_stepN_*` so it is reported and can be run
alone (`pytest -k step3`). The steps:

  1. `notes-app.sql` is written and opens with the *Start Block* mandated by the
     `mariadb-schema-create-script` skill → the plugin's skills reached the model.
  2. A MariaDB sandbox is reachable          → the MCP `sandbox.deploy` tool ran.
  3. The `notes-app` schema exists in it     → SQL ran through the MCP server.
  4. `notes-app-rest.sql` carries the REST DDL for `/notesApp` → the
     `mariadb-rest-service-create` skill was loaded and followed.
  5. The REST metadata schema reports the `/notesApp` service and its objects →
     the REST script really was executed against the sandbox.
  6. The event stream shows completed **MCP tool calls on the `mariadb` server**,
     and the launcher probe fired → the server was not merely configured but
     used, and it was *this plugin's* launcher that Codex spawned.

Two further tests stand apart from the workflow because they cost no model
tokens: they check that Codex *registers* the server correctly when the plugin is
installed the way a user installs it (see the module docstring of
`lib/codex_cli.py` for why marketplace discovery is the interesting part).

Deselected by default (see pyproject.toml `addopts`). It self-skips unless the
whole toolchain is present: the `codex` CLI (override: CODEX_BIN) already
authenticated (`codex login`), a `mariadb-shell` the launcher can resolve (on
PATH or via MARIADB_SHELL_BIN), and PyMySQL to inspect the sandbox.

Knobs (all optional): CODEX_BIN, E2E_MODEL, E2E_TIMEOUT, E2E_SANDBOX_HOST,
E2E_SANDBOX_PORT, E2E_SANDBOX_USER, E2E_SANDBOX_PASSWORD.
"""

from __future__ import annotations

import os
import re
import socket
import time
from pathlib import Path

import pytest

from lib import codex_cli
from lib.mcp_stdio import MCPStdioClient

pytestmark = pytest.mark.e2e

# File names the model is asked to produce.
SCHEMA_SQL = "notes-app.sql"
REST_SQL = "notes-app-rest.sql"
REST_SERVICE_PATH = "/notesApp"

SANDBOX_HOST = os.environ.get("E2E_SANDBOX_HOST", "127.0.0.1")
SANDBOX_USER = os.environ.get("E2E_SANDBOX_USER", "root")
SANDBOX_PASSWORD = os.environ.get("E2E_SANDBOX_PASSWORD", "test")
MODEL = os.environ.get("E2E_MODEL") or None  # None => whatever codex is configured for
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "900"))

# The sandbox schema may be created as `notes-app` or normalized to `notes_app`.
SCHEMA_CANDIDATES = ("notes-app", "notes_app")
# REST metadata schema created by CONFIGURE REST METADATA (unchanged in the fork).
REST_META_SCHEMA = "mariadb_rest_service"

# The two lines that uniquely identify the skill's mandated Start Block.
START_BLOCK_MARKERS = ("@OLD_UNIQUE_CHECKS", "SET NAMES utf8mb4")


def _build_prompt(port: int, password: str) -> str:
    # The root password is pinned so the test can both connect to verify the
    # schema and stop the sandbox for teardown (a blank one is rejected).
    return (
        "Work in the current directory and complete every step in order. Use the "
        "MariaDB MCP server for all database work.\n\n"
        "1. Create a MariaDB database schema named notes-app for a note-taking "
        f"app and store it in a {SCHEMA_SQL} file.\n"
        f"2. Spin up a sandbox instance on port {port} with root password "
        f"'{password}', connect to it and run {SCHEMA_SQL} via the MCP server.\n"
        f"3. Create a second SQL script named {REST_SQL} that sets up the MariaDB "
        "REST Service for the notes-app schema: configure the REST metadata, "
        f"create a REST service with the request path {REST_SERVICE_PATH}, add a "
        "REST schema for the notes-app database schema, and add REST endpoints "
        "for its objects (a REST data mapping view for each table, and REST "
        "procedures/functions for any stored routines).\n"
        f"4. Run {REST_SQL} against the same sandbox via the MCP server.\n"
        "5. Confirm the result by running SHOW REST SERVICES and the other SHOW "
        "REST commands against the sandbox via the MCP server."
    )


def _pick_port() -> int:
    override = os.environ.get("E2E_SANDBOX_PORT")
    if override:
        return int(override)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _parse_rest_paths(sql: str) -> dict:
    """Pull the service, schema and endpoint request paths out of the REST script."""
    service = re.search(r"(?im)\bREST\s+SERVICE\s+(?:IF\s+NOT\s+EXISTS\s+)?(/[^\s;{]+)", sql)
    schema = re.search(r"(?im)\bREST\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?(/[^\s;{]+)", sql)
    endpoints = re.findall(
        r"(?im)\bREST\s+(?:DATA\s+)?(?:MAPPING\s+)?(?:VIEW|PROCEDURE|FUNCTION)\s+"
        r"(?:IF\s+NOT\s+EXISTS\s+)?(/[^\s;{]+)",
        sql,
    )
    return {
        "service": service.group(1) if service else "",
        "schema": schema.group(1) if schema else "",
        "endpoints": sorted(set(endpoints)),
    }


def _sandbox_query(port: int, sql: str, retries: int = 10, delay: float = 1.0):
    """Run one query against the sandbox; None when it stays unreachable."""
    import pymysql

    last_exc = None
    for _ in range(retries):
        try:
            conn = pymysql.connect(
                host=SANDBOX_HOST,
                port=port,
                user=SANDBOX_USER,
                password=SANDBOX_PASSWORD,
                connect_timeout=3,
                read_timeout=5,
            )
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    return cur.fetchall()
            finally:
                conn.close()
        except Exception as exc:  # sandbox may still be starting
            last_exc = exc
            time.sleep(delay)
    print(f"sandbox unreachable at {SANDBOX_HOST}:{port}: {last_exc}")
    return None


def _sandbox_schemas(port: int) -> list[str]:
    rows = _sandbox_query(port, "SELECT schema_name FROM information_schema.schemata")
    return [r[0] for r in rows] if rows else []


def _rest_metadata(port: int) -> dict | None:
    """{service paths, #objects} from the REST metadata schema, or None."""
    services = _sandbox_query(port, f"SELECT url_context_root FROM {REST_META_SCHEMA}.service")
    if services is None:
        return None
    objects = _sandbox_query(port, f"SELECT COUNT(*) FROM {REST_META_SCHEMA}.rest_object")
    return {
        "services": [r[0] for r in services],
        "objects": int(objects[0][0]) if objects else 0,
    }


def _teardown_sandbox(port: int, password: str) -> None:
    """Best-effort: stop then drop the sandbox with real MCP calls.

    `sandbox.delete` refuses to remove a *running* instance, so it is stopped
    first — gracefully via `sandbox.stop` (which needs the root password), and
    forcibly via `sandbox.kill` when that fails. Never raises: teardown must not
    mask the test result, and it runs even when the model run timed out with the
    sandbox already up.
    """
    def _errored(result) -> bool:
        return isinstance(result, dict) and result.get("isError")

    try:
        with MCPStdioClient([str(codex_cli.LAUNCHER)], env=dict(os.environ), timeout=60) as client:
            stop = client.call_tool("sandbox.stop", {"port": port, "password": password})
            if _errored(stop):
                print(f"sandbox.stop errored ({stop}); forcing sandbox.kill")
                client.call_tool("sandbox.kill", {"port": port})
            result = client.call_tool("sandbox.delete", {"port": port})
            if _errored(result):
                client.call_tool("sandbox.kill", {"port": port})
                result = client.call_tool("sandbox.delete", {"port": port})
            print(f"sandbox.delete via MCP -> {result}")
    except Exception as exc:
        print(f"sandbox teardown via MCP failed: {exc}")


# --------------------------------------------------------------------------- #
# The workflow runs ONCE in a module-scoped fixture; each step asserts one side
# effect of that shared run.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def workflow(tmp_path_factory):
    reason = codex_cli.missing_prerequisite()
    if reason:
        pytest.skip(reason)
    try:
        import pymysql  # noqa: F401
    except ImportError:
        pytest.skip("PyMySQL not installed — cannot inspect the sandbox")

    root = tmp_path_factory.mktemp("codex_rest_e2e")
    project = root / "project"
    project.mkdir()
    port = _pick_port()

    codex_home = codex_cli.prepare_codex_home(root)
    codex_cli.install_plugin(codex_home, codex_cli.REPO_ROOT)
    # Sandboxes live under ~/mysql-sandboxes/<port>; the deploy tool writes there,
    # so that root has to be allow-listed alongside the project dir.
    sandbox_root = Path.home() / "mysql-sandboxes"
    shell_home = codex_cli.prepare_shell_config_home(root, [project, sandbox_root])
    marker = root / "launcher_started"
    launcher = codex_cli.launcher_probe(root, marker)

    ctx = {"project": project, "port": port, "marker": marker}
    try:
        ctx["run"] = codex_cli.run_codex(
            _build_prompt(port, SANDBOX_PASSWORD),
            project=project,
            codex_home=codex_home,
            shell_config_home=shell_home,
            launcher=launcher,
            timeout=TIMEOUT,
            model=MODEL,
        )
        if blocked := ctx["run"].blocking_error():
            pytest.skip(f"codex could not run: {blocked}")
        yield ctx
    finally:
        _teardown_sandbox(port, SANDBOX_PASSWORD)


def test_step0_run_finished(workflow):
    """The codex run completed within the timeout (gate for the later steps)."""
    run = workflow["run"]
    assert not run.timed_out, f"codex did not finish within {TIMEOUT}s.{run.diagnostics}"


def test_step1_schema_script_written(workflow):
    """notes-app.sql exists and opens with the mariadb-schema-create-script Start Block."""
    run = workflow["run"]
    sql_path = workflow["project"] / SCHEMA_SQL
    assert sql_path.is_file(), f"{SCHEMA_SQL} was not created.{run.diagnostics}"
    sql = sql_path.read_text(encoding="utf-8")
    for marker in START_BLOCK_MARKERS:
        assert marker in sql, (
            f"{SCHEMA_SQL} is missing the Start Block marker {marker!r} required by "
            f"mariadb-schema-create-script.{run.diagnostics}"
        )
    first_ddl = re.search(r"(?im)^\s*CREATE\s+(OR\s+REPLACE\s+)?(SCHEMA|DATABASE|TABLE)", sql)
    first_marker = sql.find("@OLD_UNIQUE_CHECKS")
    assert first_ddl is None or first_marker < first_ddl.start(), (
        f"Start Block must precede the first CREATE statement.{run.diagnostics}"
    )


def test_step2_sandbox_created(workflow):
    """The MCP sandbox tool spun up a reachable MariaDB instance."""
    schemas = _sandbox_schemas(workflow["port"])
    assert schemas, (
        f"sandbox not reachable at {SANDBOX_HOST}:{workflow['port']} — the MCP sandbox "
        f"tool did not create it.{workflow['run'].diagnostics}"
    )


def test_step3_schema_loaded(workflow):
    """The generated schema script ran via MCP: the notes-app schema exists."""
    schemas = _sandbox_schemas(workflow["port"])
    assert any(s in SCHEMA_CANDIDATES for s in schemas), (
        f"none of {SCHEMA_CANDIDATES} found in sandbox schemas {schemas}; the generated "
        f"script was not run via the MCP server.{workflow['run'].diagnostics}"
    )


def test_step4_rest_script_written(workflow):
    """notes-app-rest.sql exists and carries the expected REST DDL for /notesApp."""
    run = workflow["run"]
    rest_path = workflow["project"] / REST_SQL
    assert rest_path.is_file(), f"{REST_SQL} was not created.{run.diagnostics}"
    rest_sql = rest_path.read_text(encoding="utf-8")
    assert re.search(r"(?i)\bCONFIGURE\s+REST\s+METADATA\b", rest_sql), (
        f"{REST_SQL} does not CONFIGURE REST METADATA.{run.diagnostics}"
    )
    paths = _parse_rest_paths(rest_sql)
    assert paths["service"] and "notesapp" in paths["service"].lower(), (
        f"{REST_SQL} does not create a REST service named notesApp "
        f"(parsed service path: {paths['service']!r}).{run.diagnostics}"
    )
    assert paths["schema"], f"{REST_SQL} does not create a REST schema.{run.diagnostics}"
    assert paths["endpoints"], (
        f"{REST_SQL} does not create any REST endpoints.{run.diagnostics}"
    )


def test_step5_rest_service_created(workflow):
    """The REST DDL really ran: the metadata schema reports /notesApp + its objects."""
    run = workflow["run"]
    meta = _rest_metadata(workflow["port"])
    assert meta is not None, (
        f"could not read {REST_META_SCHEMA} from the sandbox — the REST script was not "
        f"executed against it.{run.diagnostics}"
    )
    assert any("notesapp" in s.lower() for s in meta["services"]), (
        f"{REST_SERVICE_PATH} missing from {REST_META_SCHEMA}.service {meta['services']}."
        f"{run.diagnostics}"
    )
    assert meta["objects"] > 0, (
        f"no REST objects registered in {REST_META_SCHEMA}.rest_object.{run.diagnostics}"
    )


def test_step6_mcp_server_was_used(workflow):
    """Codex actually called this plugin's MariaDB MCP server, not just loaded it."""
    run = workflow["run"]
    calls = run.mcp_tool_calls()
    assert calls, (
        "the event stream contains no mcp_tool_call for the 'mariadb' server — Codex "
        f"never used the MCP server.{run.diagnostics}"
    )
    completed = run.completed_mcp_tools()
    assert completed, (
        "every mariadb MCP call failed or was cancelled: "
        f"{[(c.get('tool'), c.get('status'), c.get('error')) for c in calls]}{run.diagnostics}"
    )
    # The wrapper only writes its marker when Codex spawns *this* launcher, so a
    # server of the same name from elsewhere cannot satisfy this test.
    assert workflow["marker"].is_file(), (
        "the MariaDB MCP tools answered, but this plugin's launcher never ran — Codex "
        f"used some other 'mariadb' server.{run.diagnostics}"
    )
    assert any(t.startswith("db.") for t in completed), (
        f"no db.* tool completed; tools used: {completed}{run.diagnostics}"
    )


# --------------------------------------------------------------------------- #
# Registration, independent of the workflow (no model tokens).
#
# "Correctly registered" means two things, and they fail differently: Codex has
# to resolve `dev@mariadb` from *this repo* to the Codex plugin, and the MCP
# command it then registers has to be a runnable path rather than a placeholder
# it never expands.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def codex_home(tmp_path_factory):
    reason = codex_cli.missing_prerequisite()
    if reason:
        pytest.skip(reason)
    return codex_cli.prepare_codex_home(tmp_path_factory.mktemp("codex_reg"))


def test_repo_marketplace_resolves_the_codex_plugin(codex_home, tmp_path_factory):
    """Installing `dev@mariadb` from this repo must yield codex/dev-plugin."""
    listing = codex_cli.plugin_listing(codex_home, codex_cli.REPO_ROOT)
    rows = [ln for ln in listing.splitlines() if ln.startswith(codex_cli.PLUGIN_ID)]
    assert rows, f"codex does not see {codex_cli.PLUGIN_ID} in this repo:\n{listing}"
    assert "codex/dev-plugin" in rows[0], (
        f"codex resolved {codex_cli.PLUGIN_ID} to the wrong plugin directory:\n  {rows[0].strip()}\n"
        "Codex reads .agents/plugins/marketplace.json (falling back to "
        ".claude-plugin/marketplace.json) and never .codex-plugin/marketplace.json, so it "
        "installs the Claude plugin from this repo."
    )


def test_setup_script_registers_a_runnable_mcp_server(codex_home):
    """`setup-codex-mcp.sh` must leave Codex with a server it can actually spawn.

    This is the supported registration path on Codex 0.147, and the assertion is
    deliberately about the *stored* command rather than something the placeholder
    could be resolved into: Codex expands nothing when it spawns a plugin server,
    so a `${...}` here means "MCP startup failed: No such file or directory" at
    the first tool call. Only a literal, executable path works.
    """
    result = codex_cli.run_setup_script(codex_home)
    assert result.returncode == 0, (
        f"setup-codex-mcp.sh failed:\n{result.stdout}\n{result.stderr}"
    )

    entry = codex_cli.registered_server(codex_home)
    assert entry, f"the setup script registered no MCP server called {codex_cli.SERVER_NAME!r}"

    command = entry.get("command", "")
    assert "${" not in command, (
        f"the registered command holds a placeholder Codex never expands: {command!r}"
    )
    assert Path(command).is_file() and os.access(command, os.X_OK), (
        f"the registered MCP command is not an executable file: {command!r}"
    )
    assert Path(command).resolve() == codex_cli.LAUNCHER.resolve(), (
        f"the registered command is not this plugin's launcher: {command!r}"
    )
