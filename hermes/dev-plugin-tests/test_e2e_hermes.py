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

"""Tier 4 — end-to-end via the real Hermes CLI (opt-in: `pytest -m e2e`).

The Hermes counterpart of `pi/dev-plugin-tests/test_e2e_pi.py`. Everything runs
in one temporary Hermes profile (see `lib/hermes_cli.py`), into which the
working tree's dev plugin is installed with `hermes plugins install
<git url>#hermes/dev-plugin` — the command the README gives users.

  0. the install succeeded and left the plugin, its skills and its launcher in
     the profile, and the plugin is enabled;
  1. a schema-script run (module-scoped `workflow` fixture, one `hermes chat`):
     the model loaded one of this plugin's skills through `skill_view`, under the
     plugin's namespace — evidence from Hermes' own tool events, not the reply;
  2. `notes-app.sql` was written, and
  3. it opens with the *Start Block* the `mariadb-schema-create-script` skill
     mandates → a skill was not merely visible but followed;
  4. an MCP run (`mcp_run`): the model calls `db_list_connections` and Hermes
     reports a successful result from `mcp__mariadb__db_list_connections`, i.e.
     Hermes started the server the plugin's mcp.json declares.

No fixed model: Hermes runs whatever provider it is configured for; each run
records the model, so a failure can be read in that light.

Deselected by default (see pyproject.toml `addopts`). It self-skips unless
`hermes` is present, configured, and can reach a model — checked with a trivial
round trip inside the temporary profile.

Knobs (all optional): HERMES_BIN, HERMES_HOME, E2E_TIMEOUT.
"""

from __future__ import annotations

import json
import os
import re

import pytest

from lib import hermes_cli

pytestmark = pytest.mark.e2e

SCHEMA_SQL = "notes-app.sql"
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "900"))

# The two lines that uniquely identify the skill's mandated Start Block.
START_BLOCK_MARKERS = ("@OLD_UNIQUE_CHECKS", "SET NAMES utf8mb4")


def _build_prompt() -> str:
    # Scope pinned (two tables, one write, a one-line reply) so a slow model does
    # not wander past the timeout. The skill is described, never named, so the
    # model has to find it among the plugin's skills itself.
    return (
        f"Write a MariaDB schema create script to the file {SCHEMA_SQL} in the "
        "current directory, for a schema named notes_app with exactly two tables: "
        "notebook (id, name) and note (id, notebook_id referencing notebook, title, "
        "body). No views, no seed data and no other objects. First load the MariaDB "
        "skill on schema create script conventions from your skills and follow it, "
        "including its mandated start block.\n\n"
        "Write the file once. Do not connect to a database or run the script. "
        "Then reply with one line naming the MariaDB skills you used, and stop."
    )


@pytest.fixture(scope="module")
def profile(tmp_path_factory):
    """A temporary Hermes profile with the working tree's plugin installed."""
    reason = hermes_cli.missing_prerequisite()
    if reason:
        pytest.skip(reason)
    with hermes_cli.TemporaryProfile() as prof:
        installed = prof.install_plugin(tmp_path_factory.mktemp("hermes_plugin_src"))
        prof.install_result = installed
        reason = hermes_cli.provider_ready(prof, tmp_path_factory.mktemp("hermes_ready"))
        if reason:
            pytest.skip(reason)
        yield prof


def test_step0_plugin_installed_and_enabled(profile):
    """`hermes plugins install …#hermes/dev-plugin --enable` did its job."""
    installed = profile.install_result
    assert installed.returncode == 0, (
        f"hermes plugins install failed (exit {installed.returncode}):\n"
        f"{installed.stdout[-3000:]}\n{installed.stderr[-2000:]}"
    )
    plugin_dir = profile.installed_plugin_dir()
    assert (plugin_dir / "plugin.json").is_file(), f"no plugin.json under {plugin_dir}"
    assert (plugin_dir / "mcp.json").is_file(), f"no mcp.json under {plugin_dir}"
    assert os.access(plugin_dir / "scripts" / "mariadb-mcp-launcher.sh", os.X_OK), (
        "the installed launcher lost its executable bit; Hermes could not start the server"
    )
    shown = profile.hermes("plugins", "list", "--plain", "--no-bundled", timeout=120)
    line = next((ln for ln in shown.stdout.splitlines() if hermes_cli.PLUGIN_NAME in ln), "")
    assert line, f"{hermes_cli.PLUGIN_NAME} missing from `hermes plugins list`:\n{shown.stdout}"
    assert "disabled" not in line.lower(), f"the plugin is installed but not enabled: {line}"


@pytest.fixture(scope="module")
def workflow(tmp_path_factory, profile):
    project = tmp_path_factory.mktemp("hermes_e2e") / "project"
    project.mkdir()
    run = hermes_cli.run_hermes(profile, _build_prompt(), project=project, timeout=TIMEOUT)
    print(f"hermes e2e ran against model: {run.model()}")
    yield {"project": project, "run": run}


def test_step1_run_finished(workflow):
    """The Hermes run completed within the timeout (gate for the later steps)."""
    run = workflow["run"]
    assert not run.timed_out, f"hermes did not finish within {TIMEOUT}s.{run.diagnostics}"
    assert run.returncode == 0, f"hermes exited {run.returncode}.{run.diagnostics}"


def test_step2_a_plugin_skill_was_loaded(workflow):
    """The model loaded at least one of this plugin's skills by its namespaced name.

    Hermes namespaces a portable plugin's skills as
    `agent-plugin-mariadb-dev-<hash>:<skill>`; a `skill_view` call naming one is
    proof the installed, enabled plugin supplied it.
    """
    run = workflow["run"]
    viewed = run.plugin_skills_viewed()
    assert viewed, (
        f"no skill_view call loaded a skill of {hermes_cli.PLUGIN_NAME} "
        f"(model: {run.model()}).{run.diagnostics}"
    )
    print(f"plugin skills the model loaded: {sorted(set(viewed))}")


def test_step3_schema_script_written(workflow):
    """The run produced the requested SQL file in the project dir."""
    run = workflow["run"]
    sql_path = workflow["project"] / SCHEMA_SQL
    assert sql_path.is_file(), (
        f"{SCHEMA_SQL} was not created (model: {run.model()}).{run.diagnostics}"
    )


def test_step4_start_block_from_the_skill(workflow):
    """The script opens with the Start Block `mariadb-schema-create-script` mandates."""
    run = workflow["run"]
    sql_path = workflow["project"] / SCHEMA_SQL
    if not sql_path.is_file():
        pytest.skip("no schema script — see test_step3")
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
# MCP: the server the plugin's mcp.json declares answers a tool call.
#
# `db_list_connections` needs no arguments and no database, and succeeds with an
# empty list on a machine that has not run `mcp setup`.
# --------------------------------------------------------------------------- #
MCP_TOOL = f"mcp__{hermes_cli.SERVER_NAME}__db_list_connections"


@pytest.fixture(scope="module")
def mcp_run(tmp_path_factory, profile):
    project = tmp_path_factory.mktemp("hermes_e2e_mcp") / "project"
    project.mkdir()
    prompt = (
        f"Call the MCP tool {MCP_TOOL} exactly once, with no arguments, and reply "
        "with its raw output. Do nothing else."
    )
    return hermes_cli.run_hermes(profile, prompt, project=project, timeout=TIMEOUT, max_turns=10)


def test_step5_mcp_server_answers_a_tool_call(mcp_run):
    """Hermes started the plugin's `mariadb` server and a call to it succeeded."""
    run = mcp_run
    assert not run.timed_out and run.returncode == 0, f"hermes run failed.{run.diagnostics}"
    calls = run.mcp_tool_results()
    assert calls, (
        f"no tool of the {hermes_cli.SERVER_NAME!r} MCP server ran, so Hermes did not "
        f"connect the server the plugin's mcp.json declares (model: {run.model()})."
        f"{run.diagnostics}"
    )
    failed = [c for c in calls if c.get("is_error")]
    assert not failed, f"the mariadb MCP tool call failed: {json.dumps(failed)[:2000]}{run.diagnostics}"
