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

"""Tier 1 — static / structural checks of the vendored skills.

No DB, no LLM: fast and deterministic, suitable as the always-on CI gate.
Parametrized over every skill in the manifest (plus a few suite-wide invariants).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from lib import skills

pytestmark = pytest.mark.static

ALL_SKILLS = skills.load_skills()
STATEMENT_SKILLS = skills.statement_skills()
ADDITIONAL_SKILLS = skills.additional_skills()


def _id(s: skills.Skill) -> str:
    return s.name


# --- per-skill frontmatter / naming -----------------------------------------


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_skill_md_exists(skill: skills.Skill):
    assert skill.path.is_file(), f"missing SKILL.md at {skill.rel_path}"


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_frontmatter_has_name_and_description(skill: skills.Skill):
    fm = skill.frontmatter
    assert isinstance(fm.get("name"), str) and fm["name"].strip(), "frontmatter missing non-empty `name`"
    desc = fm.get("description")
    assert isinstance(desc, str) and len(desc.strip()) >= 20, "frontmatter missing a substantive `description`"


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_frontmatter_name_matches_dir(skill: skills.Skill):
    assert skill.frontmatter.get("name") == skill.dir_name, (
        f"frontmatter name {skill.frontmatter.get('name')!r} != directory {skill.dir_name!r}"
    )


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_manifest_name_matches_frontmatter(skill: skills.Skill):
    assert skill.name == skill.frontmatter.get("name"), (
        f"manifest name {skill.name!r} != frontmatter name {skill.frontmatter.get('name')!r}"
    )


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_description_has_use_when_trigger(skill: skills.Skill):
    # The discoverability contract: every skill tells the agent when to use it.
    assert "use when" in skill.frontmatter.get("description", "").lower(), (
        "description should contain a 'Use when …' trigger clause"
    )


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_sql_fences_balanced(skill: skills.Skill):
    assert skill.fence_count() % 2 == 0, "unbalanced ``` code fences in SKILL.md"


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_see_also_refs_resolve(skill: skills.Skill):
    known = skills.skill_names()
    dangling = {r for r in skill.see_also_refs() if r not in known}
    assert not dangling, f"See Also references unknown skills: {sorted(dangling)}"


# --- statement-skill content contract ---------------------------------------


@pytest.mark.parametrize("skill", STATEMENT_SKILLS, ids=_id)
def test_statement_has_llms_often_miss(skill: skills.Skill):
    assert skills.has_section(skill.body, "What LLMs Often Miss"), (
        "statement skills must carry a 'What LLMs Often Miss' section"
    )


@pytest.mark.parametrize("skill", STATEMENT_SKILLS, ids=_id)
def test_statement_has_runnable_sql(skill: skills.Skill):
    assert skill.sql_blocks(), "statement skills must include at least one ```sql block"


# --- suite-wide invariants ---------------------------------------------------


def test_manifest_paths_exist_on_disk():
    missing = [s.rel_path for s in ALL_SKILLS if not s.path.is_file()]
    assert not missing, f"manifest lists skills not on disk: {missing}"


def test_every_disk_skill_is_in_manifest():
    manifest_paths = {(skills.SKILLS_ROOT / s.rel_path).resolve() for s in ALL_SKILLS}
    disk_paths = {p.resolve() for p in skills.discover_disk_skills()}
    orphans = disk_paths - manifest_paths
    assert not orphans, f"SKILL.md files on disk but absent from manifest: {sorted(map(str, orphans))}"


def test_skill_names_unique():
    names = [s.name for s in ALL_SKILLS]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate skill names: {sorted(dupes)}"


def test_expected_statement_skill_count():
    # Guardrail against an unintended change to the vendored set: the count of
    # granular statement skills. Bump this when sync-skills.sh pulls a ref that
    # legitimately adds or removes statement skills.
    assert len(STATEMENT_SKILLS) == 31, f"expected 31 statement skills, found {len(STATEMENT_SKILLS)}"


# --- vendored `additional` skills match their source in this repo ------------
#
# `additional-skills/` is the editable source; the copies under each plugin's
# skills/ are vendored by scripts/sync-skills.sh. Editing the source without
# re-running that script leaves every plugin shipping stale text, which no other
# check would notice: the manifest still agrees with what is on disk, and the
# stale copy still parses. This is the check that notices.


@pytest.mark.parametrize("skill", ADDITIONAL_SKILLS, ids=_id)
def test_additional_skill_matches_its_source(skill: skills.Skill):
    sources = skills.additional_sources(skill.name)
    assert sources, (
        f"no source for the vendored {skill.name!r} under additional-skills/*/ — "
        "it was removed from (or renamed in) the source tree without re-running "
        "scripts/sync-skills.sh"
    )
    assert len(sources) == 1, (
        f"{skill.name!r} exists in more than one additional-skills/ subfolder: "
        + ", ".join(str(p.relative_to(skills.REPO_ROOT)) for p in sources)
    )
    source = sources[0]
    assert skill.path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8"), (
        f"vendored {skill.rel_path} differs from {source.relative_to(skills.REPO_ROOT)} — "
        "re-run scripts/sync-skills.sh from the repo root"
    )


# --- the SQL language server --------------------------------------------------
# .lsp.json is not checked by `claude plugin validate`, and an unknown key makes
# Claude Code reject the whole file, so its shape is pinned here.

LSP_KEYS = {
    "command", "args", "extensionToLanguage", "transport", "env",
    "initializationOptions", "settings", "workspaceFolder", "startupTimeout",
    "shutdownTimeout", "requestTimeout", "restartOnCrash", "maxRestarts",
    "diagnostics",
}

# Every plugin that ships the LSP launcher, besides claude/dev-plugin, whose
# copy is the one the others are compared with. Codex and pi have no way to
# register a language server, so they get none.
LSP_PLUGINS = [
    "claude/sql-plugin",
    "opencode/dev-plugin", "opencode/sql-plugin",
    "hermes/dev-plugin", "hermes/sql-plugin",
]
# The plugins whose config names the extensionless launchers (Windows resolves
# them to the .cmd, elsewhere they run the .sh).
WRAPPER_PLUGINS = ["claude/sql-plugin", "opencode/dev-plugin", "opencode/sql-plugin"]
SCRIPTS = skills.PLUGIN_ROOT / "scripts"


@pytest.mark.parametrize("plugin", ["dev-plugin", "sql-plugin"])
def test_lsp_json_registers_the_launcher(plugin: str):
    root = skills.REPO_ROOT / "claude" / plugin
    config = json.loads((root / ".lsp.json").read_text(encoding="utf-8"))
    assert list(config) == ["mariadb"]
    server = config["mariadb"]
    assert set(server) <= LSP_KEYS, f"unknown keys: {set(server) - LSP_KEYS}"
    assert server["extensionToLanguage"] == {".sql": "sql"}
    prefix = "${CLAUDE_PLUGIN_ROOT}/"
    assert server["command"].startswith(prefix)
    launcher = root / server["command"][len(prefix):]
    assert launcher.is_file() and os.access(launcher, os.X_OK), f"{launcher} is not an executable file"


@pytest.mark.parametrize("plugin", LSP_PLUGINS)
@pytest.mark.parametrize("script", ["mariadb-lsp-launcher.sh", "mariadb-lsp-launcher.cmd"])
def test_lsp_launcher_is_the_shared_launcher(plugin: str, script: str):
    """The LSP launcher is one script copied into every plugin that can use it."""
    ours = (skills.REPO_ROOT / plugin / "scripts" / script).read_bytes()
    assert ours == (SCRIPTS / script).read_bytes(), (
        f"{plugin}/scripts/{script} differs from claude/dev-plugin/scripts/{script}"
    )


@pytest.mark.parametrize("plugin", WRAPPER_PLUGINS)
@pytest.mark.parametrize("script", ["mariadb-mcp-launcher", "mariadb-lsp-launcher"])
def test_extensionless_launcher_is_shared(plugin: str, script: str):
    ours = (skills.REPO_ROOT / plugin / "scripts" / script).read_bytes()
    assert ours == (SCRIPTS / script).read_bytes(), (
        f"{plugin}/scripts/{script} differs from claude/dev-plugin/scripts/{script}"
    )


def _block(text: str, start: str, end: str) -> str:
    """The lines of text from the one starting with `start` to the next `end` line."""
    lines = text.splitlines()
    first = next(i for i, line in enumerate(lines) if line.startswith(start))
    last = next(i for i in range(first, len(lines)) if lines[i] == end)
    return "\n".join(lines[first:last + 1])


@pytest.mark.parametrize("ext, start, end", [
    ("sh", "version_ge()", "}"),
    ("sh", "shell_version()", "}"),
    ("cmd", ":check_version", "exit /b %errorlevel%"),
])
def test_lsp_launcher_judges_versions_as_the_mcp_launcher(ext: str, start: str, end: str):
    """The LSP launcher must accept exactly the shells the MCP launcher accepts,
    so the version code it copies from it has to stay identical."""
    mcp = (SCRIPTS / f"mariadb-mcp-launcher.{ext}").read_text(encoding="utf-8")
    lsp = (SCRIPTS / f"mariadb-lsp-launcher.{ext}").read_text(encoding="utf-8")
    assert _block(lsp, start, end) == _block(mcp, start, end), (
        f"{start} in mariadb-lsp-launcher.{ext} differs from mariadb-mcp-launcher.{ext}"
    )


@pytest.mark.skipif(os.name == "nt", reason="runs the POSIX launcher")
def test_lsp_launcher_sh_never_installs(tmp_path):
    """Only the MCP launcher installs mariadb-shell, so a harness that starts
    both servers at once downloads the package once: with no shell anywhere,
    the LSP launcher fails without fetching anything."""
    stubs, bindir = tmp_path / "stubs", tmp_path / "bin"
    stubs.mkdir()
    bindir.mkdir()
    for tool in ("curl", "wget"):
        stub = stubs / tool
        stub.write_text(f'#!/bin/sh\ntouch "{tmp_path}/{tool}-ran"\nexit 1\n')
        stub.chmod(0o755)
    path = [str(stubs), "/usr/bin", "/bin"]
    if any((Path(d) / n).exists() for d in path for n in ("mariadb-shell", "mariadb-lsp")):
        pytest.skip("a mariadb-shell or mariadb-lsp in /usr/bin or /bin")
    run = subprocess.run(
        [str(SCRIPTS / "mariadb-lsp-launcher.sh")],
        env={"HOME": str(tmp_path), "PATH": os.pathsep.join(path),
             "MARIADB_SHELL_BINDIR": str(bindir), "MARIADB_LSP_WAIT": "0"},
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )
    assert run.returncode == 1, f"expected a failure with no shell present:\n{run.stderr}"
    assert "no mariadb-lsp found" in run.stderr
    assert not list(tmp_path.glob("*-ran")), "the LSP launcher tried to download something"
    assert not list(bindir.iterdir()), "the LSP launcher put something into the bin dir"


def test_lsp_launcher_cmd_never_installs():
    """The .cmd can't run here: it must at least not carry the MCP .cmd's installer."""
    text = (SCRIPTS / "mariadb-lsp-launcher.cmd").read_text(encoding="utf-8")
    found = [n for n in ("raw.githubusercontent.com", "Invoke-WebRequest", "PS_INSTALLER", "install.ps1\"") if n in text]
    assert not found, f"mariadb-lsp-launcher.cmd must not install, but has {found}"
