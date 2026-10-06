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

"""Tier 4 — end-to-end for the MSM skills via the real Codex CLI
(opt-in: `pytest -m e2e`).

The Codex counterpart of `claude/dev-plugin-tests/test_e2e_msm_claude.py`. Unlike
the REST e2e module there is **no database and no sandbox**: `msm.prepare_release`
and `msm.generate_deployment_script` are pure on-disk operations, so every check
below is a file. Codex is driven through two releases (v1.0.0 → develop →
v1.1.0), and the assertions are about the *shape* of what MSM produced:

  1. the project was scaffolded with a development script,
  2. v1.0.0 put tables in the non-idempotent create section (140) and the VIEW in
     the idempotent one (150),
  3. the 1.0.0 deployment script was generated,
  4. the 1.0.0→1.1.0 **update script was filled** — new tables in 240 — and the
     new VIEW is in section 150 of the 1.1.0 snapshot (update section 250 is
     never deployed). SQL comments are stripped first so the empty template's
     ToDo prose cannot satisfy the assertion,
  5. the v1.1.0 deployment script composes every object from both releases,
  6. Codex registered, started and called this plugin's MariaDB MCP server (a
     completed call in the event stream, and the launcher probe fired), and
  7. it used the `msm.*` MCP tools rather than the mariadb-shell CLI — a
     non-strict xfail, since the artifacts above are correct either way and the
     choice is the model's.

The one expensive `codex exec` runs in the module-scoped `workflow` fixture; each
step is a separate test (`pytest -k step4` still drives the one run).

Deselected by default (see pyproject.toml `addopts`); self-skips unless `codex`
(authenticated) and a resolvable `mariadb-shell` are present.

Knobs (all optional): CODEX_BIN, E2E_MODEL, E2E_TIMEOUT.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from lib import codex_cli

pytestmark = pytest.mark.e2e

# The schema (and hence project/file names) the model is asked to produce.
SCHEMA = "notes_app"
PROJECT_DIRNAME = f"{SCHEMA}.msm.project"

MODEL = os.environ.get("E2E_MODEL") or None
# Scaffold + author v1.0.0 + release + develop v1.1.0 + fill + release: a long,
# many-tool-call session, so give it generous headroom.
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "1500"))


def _build_prompt() -> str:
    return (
        "Use the MariaDB Schema Management (MSM) tools of the mariadb-shell MCP "
        "server to manage a note-taking app as a versioned schema project. Work "
        "entirely inside the current directory and complete every step in order. "
        "Every MSM operation must go through the MCP tools — do not invoke the "
        "mariadb-shell command line and do not hand-write the project files.\n\n"
        f"1. Create an MSM schema project for a schema named {SCHEMA} in the "
        "current directory. For the initial version 1.0.0, author only two "
        "tables — `user` and `note` — plus a VIEW named `user_activity` that "
        "lists users ordered by their activity (their number of notes). Put the "
        "tables in the non-idempotent create section and the `user_activity` VIEW "
        "in the idempotent create section.\n"
        "2. Prepare the 1.0.0 release and generate its deployment script.\n"
        "3. Develop the next version on top of 1.0.0: add support for notebooks "
        "and tags with new `notebook` and `tag` tables, and add a VIEW named "
        "`notes_details` that joins notes with their notebook and tags.\n"
        "4. Prepare version 1.1.0. Fill the previous->1.1.0 update script with "
        "the table migration — the new `notebook` and `tag` tables in the "
        "non-idempotent update section — then generate the 1.1.0 deployment "
        "script."
    )


# --------------------------------------------------------------------------- #
# MSM artifact helpers — everything is verified from files on disk.
# --------------------------------------------------------------------------- #
def _find_project(root: Path) -> Path | None:
    """Locate the scaffolded `<schema>.msm.project` dir under the run's cwd."""
    direct = root / PROJECT_DIRNAME
    if direct.is_dir():
        return direct
    for cand in root.rglob(PROJECT_DIRNAME):
        if cand.is_dir():
            return cand
    return None


# An MSM section banner is the line `-- MSM Section NNN: Title`. Descriptive
# prose that merely mentions another section reads `-- be created inside the MSM
# Section 150: ...`, so anchoring right after the comment marker avoids those.
_BANNER_RE = re.compile(r"(?m)^--\s+MSM\s+Section\s+(\d+):")


def _sections(sql: str) -> dict:
    """Split an MSM script into {section_id: body-text-until-the-next-banner}."""
    marks = [(m.group(1), m.start()) for m in _BANNER_RE.finditer(sql)]
    out: dict = {}
    for i, (sid, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(sql)
        out[sid] = sql[start:end]
    return out


def _strip_sql_comments(sql: str) -> str:
    """Drop /* block */ and -- line comments so template ToDo text can't match."""
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return re.sub(r"(?m)--.*$", "", sql)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# --------------------------------------------------------------------------- #
# The workflow runs ONCE in a module-scoped fixture.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def workflow(tmp_path_factory):
    reason = codex_cli.missing_prerequisite()
    if reason:
        pytest.skip(reason)

    root = tmp_path_factory.mktemp("codex_msm_e2e")
    project = root / "project"
    project.mkdir()

    codex_home = codex_cli.prepare_codex_home(root)
    codex_cli.install_plugin(codex_home, codex_cli.REPO_ROOT)
    # Only the project dir needs allow-listing here: the MSM tools write the
    # schema project, and nothing deploys a sandbox in this module.
    shell_home = codex_cli.prepare_shell_config_home(root, [project])
    marker = root / "launcher_started"
    launcher = codex_cli.launcher_probe(root, marker)

    run = codex_cli.run_codex(
        _build_prompt(),
        project=project,
        codex_home=codex_home,
        shell_config_home=shell_home,
        launcher=launcher,
        timeout=TIMEOUT,
        model=MODEL,
    )
    if blocked := run.blocking_error():
        pytest.skip(f"codex could not run: {blocked}")

    yield {
        "project": project,
        "run": run,
        "marker": marker,
        "msm_project": _find_project(project),
    }


def test_step0_run_finished(workflow):
    """The codex run completed within the timeout (gate for the later steps)."""
    run = workflow["run"]
    assert not run.timed_out, f"codex did not finish within {TIMEOUT}s.{run.diagnostics}"


def test_step1_project_scaffolded(workflow):
    """msm.create_project scaffolded the schema project with a development script."""
    run = workflow["run"]
    proj = workflow["msm_project"]
    assert proj is not None, (
        f"{PROJECT_DIRNAME} was not created — msm.create_project did not run.{run.diagnostics}"
    )
    next_sql = proj / "development" / f"{SCHEMA}_next.sql"
    assert next_sql.is_file(), (
        f"development/{SCHEMA}_next.sql missing from the project.{run.diagnostics}"
    )


def test_step2_v1_0_0_uses_right_sections(workflow):
    """The v1.0.0 snapshot puts tables in create-section 140 and the VIEW in 150."""
    run = workflow["run"]
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{run.diagnostics}"
    sql = _read(proj / "releases" / "versions" / f"{SCHEMA}_1.0.0.sql")
    assert sql, (
        f"releases/versions/{SCHEMA}_1.0.0.sql was not created — the 1.0.0 release was "
        f"not prepared.{run.diagnostics}"
    )
    secs = _sections(sql)
    s140 = _strip_sql_comments(secs.get("140", ""))
    s150 = _strip_sql_comments(secs.get("150", ""))

    for table in ("user", "note"):
        assert re.search(rf"(?is)CREATE\s+TABLE.*?\b{table}", s140), (
            f"the `{table}` table is not created in section 140 of the 1.0.0 snapshot."
            f"\n--- section 140 ---\n{s140}{run.diagnostics}"
        )
    assert re.search(r"(?is)CREATE\s+(OR\s+REPLACE\s+)?.*?VIEW", s150) and "activity" in s150.lower(), (
        f"the activity VIEW is not created in section 150 of the 1.0.0 snapshot."
        f"\n--- section 150 ---\n{s150}{run.diagnostics}"
    )
    assert not re.search(r"(?is)CREATE\s+TABLE", s150), (
        f"a CREATE TABLE ended up in the idempotent section 150 (tables belong in 140)."
        f"\n--- section 150 ---\n{s150}{run.diagnostics}"
    )


def test_step3_v1_0_0_deployment_generated(workflow):
    """msm.generate_deployment_script produced the 1.0.0 deployment script."""
    run = workflow["run"]
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{run.diagnostics}"
    dep = proj / "releases" / "deployment" / f"{SCHEMA}_deployment_1.0.0.sql"
    assert dep.is_file(), (
        f"releases/deployment/{SCHEMA}_deployment_1.0.0.sql was not generated.{run.diagnostics}"
    )


def test_step4_update_script_filled(workflow):
    """The 1.0.0->1.1.0 update script was filled (tables in 240); the VIEW is in the 1.1.0 snapshot's 150."""
    run = workflow["run"]
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{run.diagnostics}"
    updates = proj / "releases" / "updates"
    upd = updates / f"{SCHEMA}_1.0.0_to_1.1.0.sql"
    if not upd.is_file():  # tolerate a differently-composed previous-version stem
        cands = sorted(updates.glob(f"{SCHEMA}_*_to_1.1.0.sql"))
        assert cands, (
            f"no 1.0.0->1.1.0 update script under releases/updates — "
            f"prepare_release(1.1.0) did not run.{run.diagnostics}"
        )
        upd = cands[0]

    secs = _sections(_read(upd))
    s240 = _strip_sql_comments(secs.get("240", ""))

    for table in ("notebook", "tag"):
        assert re.search(rf"(?is)CREATE\s+TABLE.*?\b{table}", s240), (
            f"the `{table}` table is not created in update section 240 — the update "
            f"script was not filled.\n--- section 240 ---\n{s240}{run.diagnostics}"
        )
    # The `notes_details` VIEW belongs in the idempotent section 150 of the dev
    # script, and so of the 1.1.0 snapshot: the deployment script re-runs the
    # target's section 150 on every deployment, while update section 250 is
    # never deployed.
    snap = proj / "releases" / "versions" / f"{SCHEMA}_1.1.0.sql"
    s150 = _strip_sql_comments(_sections(_read(snap)).get("150", ""))
    assert "notes_details" in s150.lower() and re.search(r"(?is)VIEW", s150), (
        f"the `notes_details` VIEW is not in section 150 of the 1.1.0 snapshot — "
        f"it must be developed in the dev script's idempotent section.\n"
        f"--- section 150 ---\n{s150}{run.diagnostics}"
    )


def test_step5_v1_1_0_deployment_has_all_objects(workflow):
    """The v1.1.0 deployment script composes the whole schema — both versions' objects."""
    run = workflow["run"]
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{run.diagnostics}"
    sql = _read(proj / "releases" / "deployment" / f"{SCHEMA}_deployment_1.1.0.sql").lower()
    assert sql, (
        f"releases/deployment/{SCHEMA}_deployment_1.1.0.sql was not generated — the "
        f"1.1.0 release was not completed.{run.diagnostics}"
    )
    required = ["user", "note", "notebook", "tag", "user_activity", "notes_details"]
    missing = [obj for obj in required if obj not in sql]
    assert not missing, (
        f"the 1.1.0 deployment script is missing objects {missing}; it should contain "
        f"every table and view from both releases.{run.diagnostics}"
    )


def test_step6_mcp_server_was_registered_and_used(workflow):
    """Codex registered, started and actually called this plugin's MariaDB MCP server.

    This is about the plugin's wiring, so it asserts only what the wiring
    controls: that Codex spawned *this* launcher (the probe wrapper writes its
    marker only then) and that at least one call to the `mariadb` server ran to
    completion. Which tools the model chooses is its own business — see
    :func:`test_step7_msm_tools_were_preferred_over_the_cli`.
    """
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
    assert workflow["marker"].is_file(), (
        "the MariaDB MCP tools answered, but this plugin's launcher never ran — Codex "
        f"used some other 'mariadb' server.{run.diagnostics}"
    )


def test_step7_msm_tools_were_preferred_over_the_cli(workflow):
    """The MSM work went through the `msm.*` MCP tools, as the prompt demands.

    This was an xfail while the runs were bypassing the server, until the cause
    turned out to be ours rather than the model's: Codex spawns MCP servers with a
    filtered environment, the isolated shell config home therefore never reached
    the server, and the `msm.*` tools rejected the project dir as unapproved — so
    the model fell back to the CLI, which has no such guard. With the environment
    declared in the server's config entry the tools work and the model uses them,
    so this is enforced. If it ever turns flaky, the model's choice is the thing
    to investigate, not the wiring.
    """
    run = workflow["run"]
    msm_tools = [t for t in run.completed_mcp_tools() if t.startswith("msm.")]
    assert msm_tools, (
        "no msm.* tool completed — the schema project was produced without the MSM MCP "
        f"tools. Completed tools: {run.completed_mcp_tools()}{run.diagnostics}"
    )
