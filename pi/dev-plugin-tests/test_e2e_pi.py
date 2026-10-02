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

"""Tier 4 — end-to-end via the real pi CLI (opt-in: `pytest -m e2e`).

The pi counterpart of `claude/dev-plugin-tests/test_e2e_claude.py`, scoped to what
pi actually offers. The single `pi -p` run happens in the module-scoped `workflow`
fixture; each side effect is its own `test_stepN_*`:

  1. the vendored skills reached the model — it can name several of them, which
     only the installed package can supply,
  2. `notes-app.sql` was written, and
  3. it opens with the *Start Block* the `mariadb-schema-create-script` skill
     mandates → a skill was not merely visible but followed.

A second run, in the `mcp_run` fixture, checks the MCP wiring: the extension
registers the `mariadb` server with Pi's built-in MCP (Pi 1.0+), and a codemode
script calls one of its tools. The assertion is on Pi's own tool event naming the
server, not on what the model says about it.

Both runs use a throwaway `PI_CODING_AGENT_DIR` holding only the user's provider
setup, so a globally installed `pi-mcp-adapter` (which replaces the built-in MCP)
cannot hide the server, and nothing is written to the user's pi config.

One deliberate difference from the Claude and Codex tiers:

* **No fixed model.** pi runs whatever provider it is configured for, which may be
  a local one; the run records which model answered, so a failure can be read in
  that light rather than blamed on the plugin.

Deselected by default (see pyproject.toml `addopts`). It self-skips unless `pi` is
present and can actually reach a model — checked with a trivial round trip, since
`pi auth check` reports `not_ready` even when runs work.

Knobs (all optional): PI_BIN, E2E_TIMEOUT.
"""

from __future__ import annotations

import os
import re

import pytest

from lib import pi_cli, skills

pytestmark = pytest.mark.e2e

SCHEMA_SQL = "notes-app.sql"
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "900"))

# The two lines that uniquely identify the skill's mandated Start Block.
START_BLOCK_MARKERS = ("@OLD_UNIQUE_CHECKS", "SET NAMES utf8mb4")



def _build_prompt() -> str:
    # The scope is pinned (two tables, nothing else, one write, a one-line reply)
    # because an open-ended "schema for a note-taking app" let a slow local model
    # keep adding views, history and seed data past the timeout. The skill is
    # described, never named, so a skill name in the reply still has to come
    # from the installed package.
    return (
        f"Write a MariaDB schema create script to the file {SCHEMA_SQL} in the "
        "current directory, for a schema named notes_app with exactly two tables: "
        "notebook (id, name) and note (id, notebook_id referencing notebook, title, "
        "body). No views, no seed data and no other objects. Follow the MariaDB "
        "schema create script conventions from your skills, including the mandated "
        "start block.\n\n"
        # Pi 1.0 gives this run the mariadb MCP server, which reaches the user's
        # saved connections. A model left to it test-runs the script against a
        # real server; the MCP wiring has its own test.
        "Write the file once. Do not connect to a database or run the script. "
        "Then reply with one line naming the MariaDB skills you used, and stop."
    )


@pytest.fixture(scope="module")
def pi_env(tmp_path_factory):
    """Environment for every pi call here: an isolated agent dir, provider checked."""
    reason = pi_cli.missing_prerequisite()
    if reason:
        pytest.skip(reason)
    agent_dir = pi_cli.isolated_agent_dir(tmp_path_factory.mktemp("pi_agent"))
    env = {**os.environ, "PI_CODING_AGENT_DIR": str(agent_dir)}
    reason = pi_cli.provider_ready(env=env)
    if reason:
        pytest.skip(reason)
    return env


def _installed_project(tmp_path_factory, name: str, env: dict):
    project = tmp_path_factory.mktemp(name) / "project"
    project.mkdir()
    installed = pi_cli.install_package(project, env=env)
    assert installed.returncode == 0, (
        f"pi install -l failed:\n{installed.stdout}\n{installed.stderr}"
    )
    return project


@pytest.fixture(scope="module")
def workflow(tmp_path_factory, pi_env):
    project = _installed_project(tmp_path_factory, "pi_e2e", pi_env)
    run = pi_cli.run_pi(_build_prompt(), project=project, timeout=TIMEOUT, extra_env=pi_env)
    print(f"pi e2e ran against model: {run.model()}")
    yield {"project": project, "run": run}


def test_step0_run_finished(workflow):
    """The pi run completed within the timeout (gate for the later steps)."""
    run = workflow["run"]
    assert not run.timed_out, f"pi did not finish within {TIMEOUT}s.{run.diagnostics}"
    assert run.returncode == 0, f"pi exited {run.returncode}.{run.diagnostics}"


def test_step1_vendored_skills_reached_the_model(workflow):
    """The model referred to skills that only this package supplies.

    Checked against the *actual* vendored names rather than a hand-picked few, and
    satisfied by a single hit: with 75 names, most of which no model would invent
    (`mariadb-schema-create-script`, `mariadb-rest-service-create`, …), one is
    enough to show the package's skills were in context. Asking a model to
    reproduce a fixed list is a test of its obedience, not of the wiring — a weak
    local provider named one skill and did the work correctly, which is a pass,
    not a failure. The substantive evidence is test_step3.
    """
    run = workflow["run"]
    text = run.assistant_text().lower()
    named = sorted(name for name in skills.skill_names() if name.lower() in text)
    assert named, (
        "the model named none of this package's 75 vendored skills, so pi did not put "
        f"them in context (model: {run.model()}).{run.diagnostics}"
    )
    print(f"skills the model referred to: {named}")


def test_step2_schema_script_written(workflow):
    """The run produced the requested SQL file in the project dir."""
    run = workflow["run"]
    sql_path = workflow["project"] / SCHEMA_SQL
    assert sql_path.is_file(), (
        f"{SCHEMA_SQL} was not created (model: {run.model()}).{run.diagnostics}"
    )


def test_step3_start_block_from_the_skill(workflow):
    """The script opens with the Start Block `mariadb-schema-create-script` mandates."""
    run = workflow["run"]
    sql_path = workflow["project"] / SCHEMA_SQL
    if not sql_path.is_file():
        pytest.skip("no schema script — see test_step2")
    sql = sql_path.read_text(encoding="utf-8")
    for marker in START_BLOCK_MARKERS:
        assert marker in sql, (
            f"{SCHEMA_SQL} is missing the Start Block marker {marker!r} required by "
            f"mariadb-schema-create-script (model: {run.model()}).{run.diagnostics}"
        )
    first_ddl = re.search(r"(?im)^\s*CREATE\s+(OR\s+REPLACE\s+)?(SCHEMA|DATABASE|TABLE)", sql)
    first_marker = sql.find("@OLD_UNIQUE_CHECKS")
    assert first_ddl is None or first_marker < first_ddl.start(), (
        f"Start Block must precede the first CREATE statement.{run.diagnostics}"
    )


# --------------------------------------------------------------------------- #
# MCP: the server the extension registers answers a tool call.
#
# The prompt hands the model the exact codemode script, so the run tests the
# wiring rather than the model's skill at writing codemode. `db.list_connections`
# needs no arguments and no server, and succeeds with an empty list.
# --------------------------------------------------------------------------- #
MCP_SCRIPT = (
    "const r = await tools.mcp__mariadb__db_list_connections({}); "
    "console.log(JSON.stringify(r));"
)


@pytest.fixture(scope="module")
def mcp_run(tmp_path_factory, pi_env):
    project = _installed_project(tmp_path_factory, "pi_e2e_mcp", pi_env)
    prompt = (
        "Run exactly this codemode script and nothing else, then reply with its "
        f"output verbatim:\n{MCP_SCRIPT}"
    )
    return pi_cli.run_pi(prompt, project=project, timeout=TIMEOUT, extra_env=pi_env)


def test_mcp_server_answers_a_tool_call(mcp_run):
    """Pi connected the `mariadb` server the extension registered and called it."""
    run = mcp_run
    assert not run.timed_out and run.returncode == 0, f"pi run failed.{run.diagnostics}"
    calls = run.mcp_tool_results()
    assert calls, (
        f"no tool of the {pi_cli.SERVER_NAME!r} MCP server ran, so Pi did not connect the "
        f"server src/index.ts registers (model: {run.model()}).{run.diagnostics}"
    )
    failed = [c for c in calls if c.get("isError")]
    assert not failed, f"the mariadb MCP tool call failed: {failed}{run.diagnostics}"
