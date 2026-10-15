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

"""Tier 4 — end-to-end via the real Claude Code CLI (opt-in: `pytest -m e2e`).

Unlike the other tiers (which check the skills statically, run their SQL, or
prompt the API directly), this one drives the actual `claude` binary with the
**dev-plugin loaded** and its **mariadb-shell MCP server wired in**, then proves
the whole stack worked by its side effects. The single (expensive) claude run
happens once in the module-scoped `workflow` fixture; each side effect below is
a separate `test_stepN_*` so it is reported and can be run individually
(`pytest -k step3`). The steps:

  1. `notes-app.sql` is written and opens with the *Start Block* mandated by the
     `mariadb-schema-create-script` skill  → the skill was loaded and followed.
  2. A MariaDB sandbox is reachable on port 33310                → the MCP
     `sandbox`/create tool ran.
  3. The `notes-app` schema exists inside that sandbox           → the MCP SQL
     execution ran the generated script.
  4. `notes-app-rest.sql` is written with the REST DDL for a `/notesApp` service
     → the `mariadb-rest-service-create` skill was loaded and followed.
  5. Running `SHOW REST SERVICES` (+ SCHEMAS/VIEWS/PROCEDURES/FUNCTIONS) against
     the sandbox reports the `/notesApp` service and its endpoints  → the REST
     script was run via the MCP server. `SHOW REST ...` are mariadb-shell DDL
     extensions, so they are executed through the MCP server (a plain SQL
     connection can't parse them); a `mariadb_rest_service` query is the
     fallback when the server's SQL tool can't be resolved.

Teardown drops the sandbox with a real `sandbox.delete` MCP call (discovered
from the server's own tools/list, so we don't hardcode the arg schema).

Deselected by default (see pyproject.toml `addopts`). It self-skips unless the
whole toolchain is present:
  * the `claude` CLI on PATH (override: CLAUDE_BIN), already authenticated —
    either via a logged-in session or ANTHROPIC_API_KEY,
  * a `mariadb-shell` the launcher can resolve — on PATH at a version >= the
    plugin's pin, or via MARIADB_SHELL_BIN,
  * PyMySQL, to inspect the sandbox.

Knobs (all optional): CLAUDE_BIN, E2E_MODEL, E2E_TIMEOUT, E2E_SANDBOX_HOST,
E2E_SANDBOX_PORT, E2E_SANDBOX_USER, E2E_SANDBOX_PASSWORD.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path

import pytest

from lib.mcp_stdio import MCPStdioClient

pytestmark = pytest.mark.e2e

PLUGIN_DIR = (Path(__file__).resolve().parent.parent / "dev-plugin").resolve()
LAUNCHER = PLUGIN_DIR / "scripts" / "mariadb-mcp-launcher.sh"

# File names the model is asked to produce.
SCHEMA_SQL = "notes-app.sql"
REST_SQL = "notes-app-rest.sql"
# The request path of the REST service the model must create.
REST_SERVICE_PATH = "/notesApp"


def _build_prompt(port: int, password: str) -> str:
    # The root password is pinned so the test can both connect to verify the
    # schema and stop the sandbox for teardown (sandbox.deploy sets a password;
    # a blank one is rejected on connect).
    return (
        "Work in the current directory and complete every step in order.\n\n"
        "1. Create a MariaDB database schema named notes-app for a note-taking "
        f"app and store it in a {SCHEMA_SQL} file.\n"
        f"2. Spin up a sandbox instance on port {port} with root password "
        f"'{password}', connect to it and run {SCHEMA_SQL} via the MCP server.\n"
        f"3. Create a second SQL script named {REST_SQL} that sets up the "
        "MariaDB REST Service for the notes-app schema: configure the REST "
        f"metadata, create a REST service with the request path {REST_SERVICE_PATH}, "
        "add a REST schema for the notes-app database schema, and add REST "
        "endpoints for its objects (a REST data mapping view for each table, and "
        "REST procedures/functions for any stored routines).\n"
        f"4. Run {REST_SQL} against the same sandbox via the MCP server.\n"
        "5. Confirm the result by running SHOW REST SERVICES and the other SHOW "
        "REST commands (SHOW REST SCHEMAS, SHOW REST VIEWS, SHOW REST PROCEDURES, "
        "SHOW REST FUNCTIONS) against the sandbox via the MCP server."
    )


def _pick_port() -> int:
    """The sandbox port: an explicit E2E_SANDBOX_PORT, else a free ephemeral one."""
    override = os.environ.get("E2E_SANDBOX_PORT")
    if override:
        return int(override)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# The two lines that uniquely identify the skill's mandated Start Block.
START_BLOCK_MARKERS = (
    "@OLD_UNIQUE_CHECKS",
    "SET NAMES utf8mb4",
)

SANDBOX_HOST = os.environ.get("E2E_SANDBOX_HOST", "127.0.0.1")
SANDBOX_USER = os.environ.get("E2E_SANDBOX_USER", "root")
SANDBOX_PASSWORD = os.environ.get("E2E_SANDBOX_PASSWORD", "test")
MODEL = os.environ.get("E2E_MODEL", "claude-opus-4-8")
# Two scripts + a sandbox spin-up + SHOW verification: give it more headroom.
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "900"))

# The sandbox schema may be created as `notes-app` or normalized to `notes_app`.
SCHEMA_CANDIDATES = ("notes-app", "notes_app")

# REST metadata schema created by CONFIGURE REST METADATA (unchanged in the fork).
REST_META_SCHEMA = "mariadb_rest_service"

# Keys the SQL-execution MCP tool's argument is likely called.
_SQL_ARG_NAMES = ("sql", "statement", "statements", "query", "script", "command", "code", "stmt")


# --------------------------------------------------------------------------- #
# Prerequisite gates — skip (never fail) when the toolchain is absent.
# --------------------------------------------------------------------------- #
def _claude_bin() -> str:
    return os.environ.get("CLAUDE_BIN") or shutil.which("claude") or ""


def _launcher_env() -> dict:
    """Env for the MCP launcher: inherit, and let it resolve mariadb-shell."""
    return dict(os.environ)


def _mariadb_shell_resolvable() -> bool:
    if os.environ.get("MARIADB_SHELL_BIN"):
        return True
    return shutil.which("mariadb-shell") is not None


def _require_toolchain():
    if not _claude_bin():
        pytest.skip("claude CLI not found (set CLAUDE_BIN or add it to PATH)")
    # No ANTHROPIC_API_KEY gate: a ready `claude` may authenticate via a
    # logged-in session instead. If it can't reach the model, the run fails
    # (surfacing claude's own auth error) rather than silently skipping.
    if not _mariadb_shell_resolvable():
        pytest.skip("mariadb-shell not resolvable (set MARIADB_SHELL_BIN or put it on PATH)")
    if not LAUNCHER.is_file():
        pytest.skip(f"launcher missing at {LAUNCHER}")
    try:
        import pymysql  # noqa: F401
    except ImportError:
        pytest.skip("PyMySQL not installed — cannot inspect the sandbox")


# --------------------------------------------------------------------------- #
# Wiring: an isolated project dir with the plugin's skills + MCP config.
# --------------------------------------------------------------------------- #
def _write_mcp_config(dest: Path) -> Path:
    """Materialize the plugin's .mcp.json with ${CLAUDE_PLUGIN_ROOT} resolved."""
    raw = (PLUGIN_DIR / ".mcp.json").read_text(encoding="utf-8")
    resolved = raw.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_DIR))
    out = dest / "mcp.json"
    out.write_text(resolved, encoding="utf-8")
    return out


def _expose_skills(project: Path) -> None:
    """Make the plugin's skills discoverable as project skills."""
    skills_link = project / ".claude" / "skills"
    skills_link.parent.mkdir(parents=True, exist_ok=True)
    skills_link.symlink_to(PLUGIN_DIR / "skills", target_is_directory=True)


def _run_claude(project: Path, mcp_config: Path, prompt: str) -> subprocess.CompletedProcess:
    cmd = [
        _claude_bin(),
        "-p", prompt,
        "--model", MODEL,
        "--mcp-config", str(mcp_config),
        "--strict-mcp-config",              # ignore any user/global MCP servers
        "--dangerously-skip-permissions",   # non-interactive; sandboxed test box
    ]
    return subprocess.run(
        cmd,
        cwd=project,
        env=_launcher_env(),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
    )


# --------------------------------------------------------------------------- #
# Sandbox inspection + teardown.
# --------------------------------------------------------------------------- #
def _sandbox_schemas(port: int, retries: int = 10, delay: float = 1.0) -> list[str]:
    """Connect to the sandbox and return its schema names ([] if unreachable)."""
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
                    cur.execute("SELECT schema_name FROM information_schema.schemata")
                    return [row[0] for row in cur.fetchall()]
            finally:
                conn.close()
        except Exception as exc:  # sandbox may still be starting
            last_exc = exc
            time.sleep(delay)
    print(f"sandbox unreachable at {SANDBOX_HOST}:{port}: {last_exc}")
    return []


def _teardown_sandbox(port: int, password: str) -> None:
    """Best-effort: stop then drop the sandbox with real MCP calls.

    sandbox.delete refuses to remove a *running* instance, so it must be stopped
    first (gracefully via sandbox.stop, which needs the root password; forcibly
    via sandbox.kill as a fallback if the password is wrong or stop hangs).
    """
    def _errored(result) -> bool:
        return isinstance(result, dict) and result.get("isError")

    try:
        with MCPStdioClient([str(LAUNCHER)], env=_launcher_env(), timeout=60) as client:
            stop = client.call_tool("sandbox.stop", {"port": port, "password": password})
            if _errored(stop):
                print(f"sandbox.stop errored ({stop}); forcing sandbox.kill")
                client.call_tool("sandbox.kill", {"port": port})
            result = client.call_tool("sandbox.delete", {"port": port})
            if _errored(result):  # still running? kill and retry once
                client.call_tool("sandbox.kill", {"port": port})
                result = client.call_tool("sandbox.delete", {"port": port})
            print(f"sandbox.delete via MCP -> {result}")
    except Exception as exc:  # never let teardown mask the test result
        print(f"sandbox teardown via MCP failed: {exc}")


# --------------------------------------------------------------------------- #
# REST verification helpers.
#
# `SHOW REST ...` are mariadb-shell DDL extensions — a plain MySQL connection
# cannot parse them — so they run through the MCP server's SQL-execution tool.
# We discover that tool from the server's tools/list at runtime rather than
# hardcode its name/schema (the server is the authority). If it can't be
# resolved, we fall back to querying the REST metadata schema directly.
# --------------------------------------------------------------------------- #
def _parse_rest_paths(sql: str) -> dict:
    """Pull the service, schema and endpoint request paths out of the REST script."""
    service = re.search(
        r"(?im)\bREST\s+SERVICE\s+(?:IF\s+NOT\s+EXISTS\s+)?(/[^\s;{]+)", sql
    )
    schema = re.search(
        r"(?im)\bREST\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?(/[^\s;{]+)", sql
    )
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


def _find_sql_tool(tools: list[dict]) -> dict | None:
    """Rank the server's tools and return the one that executes SQL, if any."""
    best, best_score = None, 0
    for t in tools:
        name = (t.get("name") or "").lower()
        desc = (t.get("description") or "").lower()
        score = 0
        if "sql" in name:
            score += 4
        if any(k in name for k in ("execute", "exec", "run", "query", "statement")):
            score += 2
        if "sql" in desc:
            score += 1
        if score > best_score:
            best, best_score = t, score
    return best if best_score > 0 else None


def _build_sql_args(tool: dict, sql: str, port: int, password: str) -> dict:
    """Fill the SQL tool's arguments from its advertised inputSchema, heuristically."""
    props = ((tool.get("inputSchema") or {}).get("properties")) or {}
    if not props:  # server advertised no schema — best guess
        return {"sql": sql, "port": port, "password": password}

    args: dict = {}
    for pname, spec in props.items():
        low = pname.lower()
        if low.endswith("port"):
            args[pname] = port
        elif "password" in low or low in ("passwd", "pass", "pwd"):
            args[pname] = password
        elif low in _SQL_ARG_NAMES:
            args[pname] = sql
        elif low.endswith("host"):
            args[pname] = SANDBOX_HOST
        elif low in ("user", "username"):
            args[pname] = SANDBOX_USER
        elif low in ("uri", "url", "connection", "connection_string", "connectionstring"):
            args[pname] = f"{SANDBOX_USER}:{password}@{SANDBOX_HOST}:{port}"

    # Make sure the SQL made it in even if no name matched exactly.
    if not any(k.lower() in _SQL_ARG_NAMES for k in args):
        for pname, spec in props.items():
            if pname not in args and (spec or {}).get("type") == "string":
                args[pname] = sql
                break
    return args


def _mcp_flatten_text(result) -> str:
    """Flatten an MCP tools/call result to plain text."""
    if not isinstance(result, dict):
        return str(result)
    parts = [
        item.get("text", "")
        for item in (result.get("content") or [])
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    return "\n".join(p for p in parts if p) or json.dumps(result)


def _rest_via_show(port: int, password: str, paths: dict) -> dict | None:
    """Run the SHOW REST commands through the MCP server; None if not possible."""
    svc = paths.get("service") or REST_SERVICE_PATH
    sch = paths.get("schema")
    try:
        with MCPStdioClient([str(LAUNCHER)], env=_launcher_env(), timeout=120) as client:
            tool = _find_sql_tool(client.list_tools())
            if not tool:
                print("no SQL-execution MCP tool found; falling back to metadata query")
                return None

            def run(sql: str) -> str:
                res = client.call_tool(tool["name"], _build_sql_args(tool, sql, port, password))
                if isinstance(res, dict) and res.get("isError"):
                    return ""
                return _mcp_flatten_text(res)

            out = {"services": run("SHOW REST SERVICES;")}
            if svc:
                out["schemas"] = run(f"SHOW REST SCHEMAS FROM SERVICE {svc};")
            if svc and sch:
                sel = f"FROM SERVICE {svc} SCHEMA {sch}"
                out["views"] = run(f"SHOW REST VIEWS {sel};")
                out["procedures"] = run(f"SHOW REST PROCEDURES {sel};")
                out["functions"] = run(f"SHOW REST FUNCTIONS {sel};")
            # If even SHOW REST SERVICES yielded nothing, treat as unavailable.
            return out if out.get("services") else None
    except Exception as exc:
        print(f"SHOW REST via MCP failed: {exc}")
        return None


def _rest_via_metadata(port: int) -> dict | None:
    """Fallback: read the REST metadata tables directly ({service paths, #objects})."""
    import pymysql

    try:
        conn = pymysql.connect(
            host=SANDBOX_HOST,
            port=port,
            user=SANDBOX_USER,
            password=SANDBOX_PASSWORD,
            connect_timeout=3,
            read_timeout=5,
        )
    except Exception as exc:
        print(f"metadata query: sandbox unreachable: {exc}")
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT url_context_root FROM {REST_META_SCHEMA}.service")
            services = [row[0] for row in cur.fetchall()]
            cur.execute(f"SELECT COUNT(*) FROM {REST_META_SCHEMA}.rest_object")
            objects = cur.fetchone()[0]
        return {"services": services, "objects": int(objects)}
    except Exception as exc:  # metadata schema absent / different layout
        print(f"metadata query failed: {exc}")
        return None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# The workflow runs ONCE (a single, expensive `claude` invocation) in a
# module-scoped fixture; each step below is then a separate, individually
# reportable test that asserts one side effect of that shared run. Run one step
# in isolation with `pytest -k step3` — the fixture still drives the one claude
# run, so the artifacts/sandbox it inspects exist.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def workflow(tmp_path_factory):
    """Drive claude once; expose the project dir, port, and run outcome to steps.

    The sandbox is always torn down at module teardown, even if the run timed
    out (claude may have created it before being killed).
    """
    _require_toolchain()

    port = _pick_port()
    project = tmp_path_factory.mktemp("notes_app_e2e")
    mcp_config = _write_mcp_config(project)
    _expose_skills(project)

    ctx = {"project": project, "port": port, "timed_out": False, "diagnostics": ""}
    try:
        try:
            proc = _run_claude(project, mcp_config, _build_prompt(port, SANDBOX_PASSWORD))
            ctx["diagnostics"] = (
                f"\n--- claude stdout ---\n{proc.stdout}\n--- claude stderr ---\n{proc.stderr}"
            )
        except subprocess.TimeoutExpired:
            ctx["timed_out"] = True
            ctx["diagnostics"] = f"\nclaude did not finish within {TIMEOUT}s"
        yield ctx
    finally:
        _teardown_sandbox(port, SANDBOX_PASSWORD)


def test_step0_run_finished(workflow):
    """The claude run completed within the timeout (gate for the later steps)."""
    assert not workflow["timed_out"], (
        f"claude did not finish within {TIMEOUT}s.{workflow['diagnostics']}"
    )


def test_step1_schema_script_written(workflow):
    """notes-app.sql exists and opens with the mariadb-schema-create-script Start Block."""
    diagnostics = workflow["diagnostics"]
    sql_path = workflow["project"] / SCHEMA_SQL
    assert sql_path.is_file(), f"{SCHEMA_SQL} was not created.{diagnostics}"
    sql = sql_path.read_text(encoding="utf-8")
    for marker in START_BLOCK_MARKERS:
        assert marker in sql, (
            f"{SCHEMA_SQL} is missing the Start Block marker {marker!r} "
            f"required by mariadb-schema-create-script.{diagnostics}"
        )
    # Start Block must be at the top, before any DDL.
    first_ddl = re.search(r"(?im)^\s*CREATE\s+(OR\s+REPLACE\s+)?(SCHEMA|DATABASE|TABLE)", sql)
    first_marker = sql.find("@OLD_UNIQUE_CHECKS")
    assert first_ddl is None or first_marker < first_ddl.start(), (
        f"Start Block must precede the first CREATE statement.{diagnostics}"
    )


def test_step2_sandbox_created(workflow):
    """The MCP sandbox tool spun up a reachable MariaDB instance."""
    schemas = _sandbox_schemas(workflow["port"])
    assert schemas, (
        f"sandbox not reachable at {SANDBOX_HOST}:{workflow['port']} — the MCP "
        f"sandbox tool did not create it.{workflow['diagnostics']}"
    )


def test_step3_schema_loaded(workflow):
    """The generated schema script ran via MCP: the notes-app schema exists."""
    schemas = _sandbox_schemas(workflow["port"])
    assert any(s in SCHEMA_CANDIDATES for s in schemas), (
        f"none of {SCHEMA_CANDIDATES} found in sandbox schemas {schemas}; the "
        f"generated script was not run via the MCP server.{workflow['diagnostics']}"
    )


def test_step4_rest_script_written(workflow):
    """notes-app-rest.sql exists and carries the expected REST DDL for /notesApp."""
    diagnostics = workflow["diagnostics"]
    rest_path = workflow["project"] / REST_SQL
    assert rest_path.is_file(), f"{REST_SQL} was not created.{diagnostics}"
    rest_sql = rest_path.read_text(encoding="utf-8")
    assert re.search(r"(?i)\bCONFIGURE\s+REST\s+METADATA\b", rest_sql), (
        f"{REST_SQL} does not CONFIGURE REST METADATA.{diagnostics}"
    )
    paths = _parse_rest_paths(rest_sql)
    assert paths["service"] and "notesapp" in paths["service"].lower(), (
        f"{REST_SQL} does not create a REST service named notesApp "
        f"(parsed service path: {paths['service']!r}).{diagnostics}"
    )
    assert paths["schema"], f"{REST_SQL} does not create a REST schema.{diagnostics}"
    assert paths["endpoints"], (
        f"{REST_SQL} does not create any REST endpoints (views/procedures/"
        f"functions).{diagnostics}"
    )


def test_step5_rest_service_created(workflow):
    """The REST script ran against the sandbox: /notesApp + its endpoints exist.

    Verified primarily through the SHOW REST commands run via the MCP server
    (they are mariadb-shell DDL extensions), with a mariadb_rest_service
    query as the fallback.
    """
    diagnostics = workflow["diagnostics"]
    rest_path = workflow["project"] / REST_SQL
    if not rest_path.is_file():
        pytest.fail(f"{REST_SQL} was not created — cannot verify the service.{diagnostics}")
    paths = _parse_rest_paths(rest_path.read_text(encoding="utf-8"))

    show = _rest_via_show(workflow["port"], SANDBOX_PASSWORD, paths)
    meta = _rest_via_metadata(workflow["port"])
    assert show or meta, (
        f"could not verify the REST service: neither the SHOW REST commands "
        f"(via MCP) nor the {REST_META_SCHEMA} metadata query returned data."
        f"{diagnostics}"
    )

    service_found = endpoint_found = False
    evidence: list[str] = []

    if show:
        services_out = show.get("services", "")
        evidence.append(f"SHOW REST SERVICES ->\n{services_out}")
        if "notesapp" in services_out.lower():
            service_found = True
        endpoint_blob = "\n".join(show.get(k, "") for k in ("views", "procedures", "functions"))
        if endpoint_blob:
            evidence.append(f"SHOW REST endpoints ->\n{endpoint_blob}")
        if any(ep.lower() in endpoint_blob.lower() for ep in paths["endpoints"]):
            endpoint_found = True

    if meta:
        evidence.append(
            f"{REST_META_SCHEMA}: services={meta['services']} objects={meta['objects']}"
        )
        if any("notesapp" in str(s).lower() for s in meta["services"]):
            service_found = True
        if meta["objects"] >= 1:
            endpoint_found = True

    evidence_text = "\n--- REST evidence ---\n" + "\n".join(evidence)
    assert service_found, (
        f"REST service {REST_SERVICE_PATH} was not found via SHOW REST SERVICES "
        f"or the metadata schema — the REST script was not run against the "
        f"sandbox.{evidence_text}{diagnostics}"
    )
    assert endpoint_found, (
        f"no REST endpoints for {REST_SERVICE_PATH} were found via the SHOW REST "
        f"commands or the metadata schema.{evidence_text}{diagnostics}"
    )
