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

"""Tier 4 — end-to-end for the MSM skills via the real Claude Code CLI
(opt-in: `pytest -m e2e`).

Sibling of `test_e2e_claude.py`, but instead of the REST skills this drives the
**MariaDB Schema Management (MSM)** skills. It asks the real `claude` binary —
dev-plugin loaded, `mariadb-shell` MCP server wired in — to take a note-taking
schema through **two versioned releases** with the `msm.*` tools, then proves the
whole stack worked by inspecting the schema project the tools wrote to disk. No
database/sandbox is involved: MSM `prepare_release` / `generate_deployment_script`
are pure on-disk operations, so every side effect is a file.

The single (expensive) claude run happens once in the module-scoped `workflow`
fixture; each side effect below is a separate `test_stepN_*` so it is reported
and can be run individually (`pytest -k step4`). The steps:

  1. `notes_app.msm.project/` is scaffolded (development/`notes_app_next.sql`)
     → `msm.create_project` ran.
  2. The v1.0.0 snapshot uses the *right sections*: the `user`/`note` tables land
     in the non-idempotent create section 140 and the activity VIEW in the
     idempotent section 150 → the section model from the skills was followed.
  3. The v1.0.0 deployment script was generated → `msm.generate_deployment_script`.
  4. The 1.0.0→1.1.0 **update script was FILLED** (the rule everyone forgets):
     new `notebook`/`tag` tables in update section 240 — not left as the empty
     template — and the `notes_details` VIEW is in section 150 of the 1.1.0
     snapshot (developed in the dev script; update section 250 is never
     deployed).
  5. The v1.1.0 deployment script contains **all** objects (both versions' tables
     and views) → the release composed the full schema.

MSM tool calls are path-gated by the MCP server's `settings.json` allow-list. To
keep the run hermetic the fixture builds an isolated shell config home via
`lib.sandbox._prepare_config_home()` (the same helper the db tier uses) that
points `MYSQLSH_USER_CONFIG_HOME` at a throwaway dir, pre-seeds that allow-list
with the project dir, and symlinks in the real config home's plugins/ — without
that last part the server has no `mcp` object registered at all and dies
immediately. So nothing touches the user's real `~/.mysqlsh` and no interactive
path-trust elicitation is needed.

Deselected by default (see pyproject.toml `addopts`). It self-skips unless the
toolchain is present:
  * the `claude` CLI on PATH (override: CLAUDE_BIN), already authenticated,
  * a `mariadb-shell` the launcher can resolve (on PATH >= the plugin's pin, or
    via MARIADB_SHELL_BIN).

Knobs (all optional): CLAUDE_BIN, E2E_MODEL, E2E_TIMEOUT.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from lib import sandbox

pytestmark = pytest.mark.e2e

PLUGIN_DIR = (Path(__file__).resolve().parent.parent / "dev-plugin").resolve()
LAUNCHER = PLUGIN_DIR / "scripts" / "mariadb-mcp-launcher.sh"

# The schema (and hence project/file names) the model is asked to produce.
SCHEMA = "notes_app"
PROJECT_DIRNAME = f"{SCHEMA}.msm.project"

MODEL = os.environ.get("E2E_MODEL", "claude-opus-4-8")
# Project scaffold + author v1.0.0 + release + develop v1.1.0 + fill + release:
# a long, many-tool-call session, so give it generous headroom.
TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "1200"))


def _build_prompt() -> str:
    return (
        "Use the MariaDB Schema Management (MSM) tools of the mariadb-shell MCP "
        "server to manage a note-taking app as a versioned schema project. Work "
        "entirely inside the current directory and complete every step in order.\n\n"
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
# Prerequisite gates — skip (never fail) when the toolchain is absent.
# --------------------------------------------------------------------------- #
def _claude_bin() -> str:
    return os.environ.get("CLAUDE_BIN") or shutil.which("claude") or ""


def _mariadb_shell_resolvable() -> bool:
    if os.environ.get("MARIADB_SHELL_BIN"):
        return True
    return shutil.which("mariadb-shell") is not None


def _require_toolchain():
    if not _claude_bin():
        pytest.skip("claude CLI not found (set CLAUDE_BIN or add it to PATH)")
    if not _mariadb_shell_resolvable():
        pytest.skip("mariadb-shell not resolvable (set MARIADB_SHELL_BIN or put it on PATH)")
    if not LAUNCHER.is_file():
        pytest.skip(f"launcher missing at {LAUNCHER}")


# --------------------------------------------------------------------------- #
# Wiring: an isolated project dir + skills + MCP config + a private shell config
# home whose allow-list already trusts the project dir. The config home itself
# comes from lib.sandbox._prepare_config_home(), which also symlinks in the
# real config home's plugins/ — without that the server has no `mcp` object
# registered at all and dies immediately (reproduced directly: `mariadb-shell
# -- mcp start-server` under a bare MYSQLSH_USER_CONFIG_HOME prints "ERROR:
# There is no object registered under name 'mcp'"), which is what surfaced here
# as claude reporting CONNECTION_CLOSED on every MSM tool call.
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


def _run_claude(project: Path, mcp_config: Path, env: dict, prompt: str) -> subprocess.CompletedProcess:
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
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
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


# An MSM section banner is the line `-- MSM Section NNN: Title` (immediately
# after a `-- ####` rule). Descriptive prose that merely mentions another
# section reads `-- be created inside the MSM Section 150: ...`, so anchoring
# `MSM Section` right after the comment marker avoids those false hits.
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
    sql = re.sub(r"(?m)--.*$", "", sql)
    return sql


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


# --------------------------------------------------------------------------- #
# The workflow runs ONCE in a module-scoped fixture; each step below asserts one
# side effect of that shared run. `pytest -k step4` still drives the one claude
# run, so the artifacts it inspects exist.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def workflow(tmp_path_factory):
    _require_toolchain()

    project = tmp_path_factory.mktemp("notes_app_msm_e2e")
    mcp_config = _write_mcp_config(project)
    _expose_skills(project)
    config_home = sandbox._prepare_config_home(project)
    env = sandbox._server_env(config_home)

    ctx = {"project": project, "timed_out": False, "diagnostics": ""}
    try:
        try:
            proc = _run_claude(project, mcp_config, env, _build_prompt())
            ctx["diagnostics"] = (
                f"\n--- claude stdout ---\n{proc.stdout}\n--- claude stderr ---\n{proc.stderr}"
            )
        except subprocess.TimeoutExpired:
            ctx["timed_out"] = True
            ctx["diagnostics"] = f"\nclaude did not finish within {TIMEOUT}s"

        # Resolve the project dir once for the steps (None if never scaffolded).
        ctx["msm_project"] = _find_project(project)
        yield ctx
    finally:
        shutil.rmtree(config_home, ignore_errors=True)


def test_step0_run_finished(workflow):
    """The claude run completed within the timeout (gate for the later steps)."""
    assert not workflow["timed_out"], (
        f"claude did not finish within {TIMEOUT}s.{workflow['diagnostics']}"
    )


def test_step1_project_scaffolded(workflow):
    """msm.create_project scaffolded the schema project with a development script."""
    proj = workflow["msm_project"]
    assert proj is not None, (
        f"{PROJECT_DIRNAME} was not created — msm.create_project did not run."
        f"{workflow['diagnostics']}"
    )
    next_sql = proj / "development" / f"{SCHEMA}_next.sql"
    assert next_sql.is_file(), (
        f"development/{SCHEMA}_next.sql missing from the project.{workflow['diagnostics']}"
    )


def test_step2_v1_0_0_uses_right_sections(workflow):
    """The v1.0.0 snapshot puts tables in create-section 140 and the VIEW in 150."""
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{workflow['diagnostics']}"
    snapshot = proj / "releases" / "versions" / f"{SCHEMA}_1.0.0.sql"
    sql = _read(snapshot)
    assert sql, (
        f"releases/versions/{SCHEMA}_1.0.0.sql was not created — the 1.0.0 "
        f"release was not prepared.{workflow['diagnostics']}"
    )
    secs = _sections(sql)
    s140 = _strip_sql_comments(secs.get("140", ""))
    s150 = _strip_sql_comments(secs.get("150", ""))

    # Tables belong in the non-idempotent section 140.
    assert re.search(r"(?is)CREATE\s+TABLE.*?\buser", s140), (
        f"the `user` table is not created in section 140 of the 1.0.0 snapshot."
        f"\n--- section 140 ---\n{s140}{workflow['diagnostics']}"
    )
    assert re.search(r"(?is)CREATE\s+TABLE.*?\bnote", s140), (
        f"the `note` table is not created in section 140 of the 1.0.0 snapshot."
        f"\n--- section 140 ---\n{s140}{workflow['diagnostics']}"
    )
    # The activity VIEW belongs in the idempotent section 150.
    assert re.search(r"(?is)CREATE\s+(OR\s+REPLACE\s+)?.*?VIEW", s150) and "activity" in s150.lower(), (
        f"the activity VIEW is not created in section 150 of the 1.0.0 snapshot."
        f"\n--- section 150 ---\n{s150}{workflow['diagnostics']}"
    )
    # And tables must NOT have been dropped into the VIEW section instead.
    assert not re.search(r"(?is)CREATE\s+TABLE", s150), (
        f"a CREATE TABLE ended up in the idempotent section 150 (tables belong "
        f"in 140).\n--- section 150 ---\n{s150}{workflow['diagnostics']}"
    )


def test_step3_v1_0_0_deployment_generated(workflow):
    """msm.generate_deployment_script produced the 1.0.0 deployment script."""
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{workflow['diagnostics']}"
    dep = proj / "releases" / "deployment" / f"{SCHEMA}_deployment_1.0.0.sql"
    assert dep.is_file(), (
        f"releases/deployment/{SCHEMA}_deployment_1.0.0.sql was not generated."
        f"{workflow['diagnostics']}"
    )


def test_step4_update_script_filled(workflow):
    """The 1.0.0->1.1.0 update script was filled (tables in 240); the VIEW is in the 1.1.0 snapshot's 150."""
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{workflow['diagnostics']}"
    updates = proj / "releases" / "updates"
    upd = updates / f"{SCHEMA}_1.0.0_to_1.1.0.sql"
    if not upd.is_file():  # tolerate a differently-composed previous-version stem
        cands = sorted(updates.glob(f"{SCHEMA}_*_to_1.1.0.sql"))
        assert cands, (
            f"no 1.0.0->1.1.0 update script under releases/updates — "
            f"prepare_release(1.1.0) did not run.{workflow['diagnostics']}"
        )
        upd = cands[0]

    secs = _sections(_read(upd))
    s240 = _strip_sql_comments(secs.get("240", ""))

    # The migration must actually be written (not the empty template): the new
    # `notebook`/`tag` tables in the non-idempotent update section 240 ...
    assert re.search(r"(?is)CREATE\s+TABLE.*?\bnotebook", s240), (
        f"the `notebook` table is not created in update section 240 — the update "
        f"script was not filled.\n--- section 240 ---\n{s240}{workflow['diagnostics']}"
    )
    assert re.search(r"(?is)CREATE\s+TABLE.*?\btag", s240), (
        f"the `tag` table is not created in update section 240 — the update "
        f"script was not filled.\n--- section 240 ---\n{s240}{workflow['diagnostics']}"
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
        f"--- section 150 ---\n{s150}{workflow['diagnostics']}"
    )


def test_step5_v1_1_0_deployment_has_all_objects(workflow):
    """The v1.1.0 deployment script composes the whole schema — both versions' objects."""
    proj = workflow["msm_project"]
    assert proj is not None, f"no MSM project.{workflow['diagnostics']}"
    dep = proj / "releases" / "deployment" / f"{SCHEMA}_deployment_1.1.0.sql"
    sql = _read(dep).lower()
    assert sql, (
        f"releases/deployment/{SCHEMA}_deployment_1.1.0.sql was not generated — "
        f"the 1.1.0 release was not completed.{workflow['diagnostics']}"
    )
    required = ["user", "note", "notebook", "tag", "user_activity", "notes_details"]
    missing = [obj for obj in required if obj not in sql]
    assert not missing, (
        f"the 1.1.0 deployment script is missing objects {missing}; it should "
        f"contain every table and view from both releases.{workflow['diagnostics']}"
    )
