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


# --- the Hermes plugin itself -----------------------------------------------
#
# Everything above is about the skills; these are about the package that makes
# Hermes load them. The plugin is a portable Agent Plugins v1 package, and Hermes
# validates it strictly when it loads it: a manifest it rejects loses the whole
# plugin, and a skill or MCP entry it rejects is skipped with only a log line.
# Neither shows up anywhere CI would look, so the rules Hermes applies
# (hermes_cli/agent_plugins.py) are restated here.

import json
import os
import re

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
PLUGIN_NAME = "mariadb-dev"
# Fields Hermes reads from plugin.json; anything else is dropped with a warning.
PLUGIN_FIELDS = {
    "$schema", "name", "version", "description", "author", "homepage", "repository",
    "license", "keywords", "extensions",
}
_PLUGIN_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
_SKILL_NAME_RE = re.compile(r"^(?!.*--)[a-z0-9]+(?:-[a-z0-9]+)*$")
LAUNCHER = "./scripts/mariadb-mcp-launcher.sh"


def _json(name: str) -> dict:
    return json.loads((skills.PLUGIN_ROOT / name).read_text(encoding="utf-8"))


def test_plugin_json_is_an_agent_plugins_v1_manifest():
    manifest = _json("plugin.json")
    assert manifest.get("$schema") == PLUGIN_SCHEMA, (
        "plugin.json must declare the Agent Plugins v1 schema, or Hermes refuses the package"
    )
    assert manifest.get("name") == PLUGIN_NAME
    assert _PLUGIN_NAME_RE.fullmatch(manifest["name"]) and len(manifest["name"]) <= 64
    unknown = set(manifest) - PLUGIN_FIELDS
    assert not unknown, f"plugin.json fields Hermes would drop: {sorted(unknown)}"
    for key in ("version", "description", "homepage", "license"):
        assert isinstance(manifest.get(key), str) and manifest[key], f"plugin.json {key!r} must be a string"
    assert set(manifest.get("author", {})) <= {"name", "email", "url"}


def test_plugin_version_matches_the_other_harnesses():
    """set-plugin-version.sh keeps every plugin in lockstep; this one must not drift."""
    claude = json.loads(
        (skills.REPO_ROOT / "claude" / "dev-plugin" / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert _json("plugin.json")["version"] == claude["version"]


def test_mcp_json_declares_the_mariadb_server():
    config = _json("mcp.json")
    assert set(config) == {"$schema", "mcpServers"}, (
        f"mcp.json may hold only $schema and mcpServers, or Hermes ignores it: {sorted(config)}"
    )
    assert config["$schema"] == MCP_SCHEMA
    server = config["mcpServers"].get("mariadb")
    assert server, "mcp.json declares no `mariadb` server"
    assert server.get("type") == "stdio"
    assert set(server) <= {"type", "command", "args", "env", "cwd"}, (
        f"unknown stdio fields make Hermes skip the server: {sorted(server)}"
    )
    # Hermes runs the command without a shell: one bare executable or a path that
    # starts with ./, resolved inside the plugin.
    assert server["command"] == LAUNCHER
    assert all(isinstance(a, str) for a in server.get("args", []))
    assert not {"PLUGIN_ROOT", "PLUGIN_DATA"} & set(server.get("env", {})), (
        "PLUGIN_ROOT and PLUGIN_DATA are reserved; Hermes rejects a server that sets them"
    )


def test_mcp_json_shell_version_matches_the_launcher_default():
    """The floor in mcp.json and the launcher's fallback move together."""
    pinned = _json("mcp.json")["mcpServers"]["mariadb"]["env"]["MARIADB_SHELL_VERSION"]
    launcher = (skills.PLUGIN_ROOT / "scripts" / "mariadb-mcp-launcher.sh").read_text(encoding="utf-8")
    default = re.search(r"MARIADB_SHELL_VERSION:-([^}]+)\}", launcher).group(1)
    assert pinned == default, f"mcp.json pins {pinned}, the launcher defaults to {default}"


@pytest.mark.parametrize("skill", ALL_SKILLS, ids=_id)
def test_skill_frontmatter_passes_hermes_validation(skill: skills.Skill):
    """Hermes skips (and only logs) a skill whose frontmatter breaks these rules."""
    fm = skill.frontmatter
    name = fm.get("name")
    assert isinstance(name, str) and 1 <= len(name) <= 64 and _SKILL_NAME_RE.fullmatch(name), (
        f"skill name {name!r} does not satisfy the Agent Skills name rules"
    )
    desc = fm.get("description")
    assert isinstance(desc, str) and 1 <= len(desc) <= 1024, "description must be 1-1024 characters"
    if "metadata" in fm:
        assert isinstance(fm["metadata"], dict) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in fm["metadata"].items()
        ), "metadata must map strings to strings"
    for key in ("license", "allowed-tools"):
        if key in fm:
            assert isinstance(fm[key], str), f"{key} must be a string"
    if "compatibility" in fm:
        assert isinstance(fm["compatibility"], str) and 1 <= len(fm["compatibility"]) <= 500


def test_no_symlinks_in_the_plugin():
    """Hermes refuses components that resolve outside the package; keep it link-free."""
    links = [p for p in skills.PLUGIN_ROOT.rglob("*") if p.is_symlink()]
    assert not links, f"symlinks in the plugin: {links}"


def test_skills_match_the_claude_dev_plugin():
    """Every harness's dev plugin vendors the same skill set (scripts/sync-skills.sh)."""
    claude_skills = skills.REPO_ROOT / "claude" / "dev-plugin" / "skills"
    ours = {p.parent.name for p in skills.SKILLS_ROOT.glob("*/SKILL.md")}
    theirs = {p.parent.name for p in claude_skills.glob("*/SKILL.md")}
    assert ours == theirs, (
        f"only here: {sorted(ours - theirs)}; only in claude: {sorted(theirs - ours)} — "
        "re-run scripts/sync-skills.sh from the repo root"
    )


def test_skills_root_holds_only_skills_and_its_manifests():
    # .gitkeep is the one file sync-skills.sh preserves when it resets skills/.
    allowed_files = {".skills-manifest.json", "skills-source.json", ".gitkeep", ".DS_Store"}
    offenders = []
    for entry in sorted(skills.SKILLS_ROOT.iterdir()):
        if entry.is_dir():
            if not (entry / "SKILL.md").is_file():
                offenders.append(f"{entry.name}/ (no SKILL.md)")
        elif entry.name not in allowed_files:
            offenders.append(entry.name)
    assert not offenders, f"unexpected entries under skills/: {offenders}"


@pytest.mark.parametrize(
    "script",
    ["mariadb-mcp-launcher.sh", "mariadb-mcp-launcher.cmd", "mariadb-lsp-launcher.sh", "mariadb-lsp-launcher.cmd"],
)
def test_shipped_scripts_are_present(script: str):
    path = skills.PLUGIN_ROOT / "scripts" / script
    assert path.is_file(), f"missing {path.relative_to(skills.REPO_ROOT)}"
    if script.endswith(".sh"):
        assert os.access(path, os.X_OK), f"{script} is not executable"


# The LSP launchers' copies are compared in the claude suite, with every
# plugin that ships them.
@pytest.mark.parametrize("script", ["mariadb-mcp-launcher.sh", "mariadb-mcp-launcher.cmd"])
def test_launcher_is_the_shared_launcher(script: str):
    """The launchers are one script copied into every plugin; keep this copy current."""
    ours = (skills.PLUGIN_ROOT / "scripts" / script).read_bytes()
    claude = (skills.REPO_ROOT / "claude" / "dev-plugin" / "scripts" / script).read_bytes()
    assert ours == claude, f"scripts/{script} differs from claude/dev-plugin/scripts/{script}"


def test_hermes_accepts_the_plugin():
    """`hermes plugins validate` passes — only where the Hermes CLI is installed."""
    import shutil
    import subprocess

    hermes = os.environ.get("HERMES_BIN") or shutil.which("hermes")
    if not hermes:
        pytest.skip("hermes CLI not found (set HERMES_BIN or add it to PATH)")
    proc = subprocess.run(
        [hermes, "plugins", "validate", str(skills.PLUGIN_ROOT)],
        capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL,
    )
    assert proc.returncode == 0 and "Validation passed" in proc.stdout, (
        f"hermes plugins validate failed:\n{proc.stdout[-3000:]}\n{proc.stderr[-1000:]}"
    )
