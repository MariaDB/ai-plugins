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


# --- the pi package itself ---------------------------------------------------
#
# Everything above is about the skills; these are about the wiring that makes pi
# load them. pi has no marketplace file: the package is declared by the
# **repo-root package.json** `pi` field, which points back into this plugin. Each
# check below corresponds to a way that has already broken, or would break
# silently — pi reports a bad manifest as a loader error at session start, which
# nothing in CI would otherwise see.


def _manifest() -> dict:
    import json

    return json.loads((skills.REPO_ROOT / "package.json").read_text(encoding="utf-8"))


def test_repo_root_package_json_declares_this_plugin():
    pi = _manifest().get("pi")
    assert isinstance(pi, dict), "repo-root package.json has no `pi` field — pi would not see a package"
    assert pi.get("extensions"), "`pi.extensions` is empty; the extension would never load"
    assert pi.get("skills"), "`pi.skills` is empty; no skills would be discovered"


def test_pi_manifest_paths_exist():
    pi = _manifest()["pi"]
    for key in ("extensions", "skills"):
        for rel in pi[key]:
            target = (skills.REPO_ROOT / rel).resolve()
            assert target.exists(), f"pi.{key} entry {rel!r} does not exist at {target}"


def test_pi_skills_entry_points_at_this_plugins_skills_root():
    """The declared skills root must be this plugin's `skills/`, not a glob.

    pi walks the directory for SKILL.md recursively, so a `/*` suffix makes it
    look one level too deep and find nothing.
    """
    declared = {(skills.REPO_ROOT / rel).resolve() for rel in _manifest()["pi"]["skills"]}
    assert skills.SKILLS_ROOT.resolve() in declared, (
        f"pi.skills {sorted(map(str, declared))} does not include {skills.SKILLS_ROOT}"
    )
    for rel in _manifest()["pi"]["skills"]:
        assert not rel.rstrip("/").endswith("*"), (
            f"pi.skills entry {rel!r} uses a glob; pi discovers SKILL.md dirs recursively "
            "from the skills root, so a glob finds nothing"
        )


def test_skills_root_holds_only_skills_and_its_manifests():
    """A stray file or dir under skills/ breaks pi's loader outright.

    Two attempts at putting documentation here have had to be reverted: an
    attribution directory without a SKILL.md made the loader fail with
    "description is required", and a skills/README.md tripped it as well. Only
    skill directories, the vendored manifest and the provenance file belong here.
    """
    allowed_files = {".skills-manifest.json", "skills-source.json", ".DS_Store"}
    offenders = []
    for entry in sorted(skills.SKILLS_ROOT.iterdir()):
        if entry.is_dir():
            if not (entry / "SKILL.md").is_file():
                offenders.append(f"{entry.name}/ (no SKILL.md)")
        elif entry.name not in allowed_files:
            offenders.append(entry.name)
    assert not offenders, (
        f"skills/ must contain only skill directories plus {sorted(allowed_files - {'.DS_Store'})}; "
        f"found: {offenders}"
    )


def test_pi_mcp_adapter_is_not_a_dependency():
    """Pi 1.0 has built-in MCP; pi-mcp-adapter would replace it, not add to it.

    An extension that registers `/mcp` (as the adapter does) switches off the
    built-in MCP support, and with it the server this package registers. Declaring
    the adapter again would tell users to install the one thing that breaks us.
    """
    deps = _manifest().get("dependencies", {})
    assert "pi-mcp-adapter" not in deps, (
        "pi-mcp-adapter is back in dependencies; it replaces Pi's built-in MCP, so the "
        "mariadb server the extension registers would never connect"
    )


def test_extension_registers_the_mcp_server():
    """The extension hands the launcher to Pi's built-in MCP as the `mariadb` server."""
    src = (skills.PLUGIN_ROOT / "src" / "index.ts").read_text(encoding="utf-8")
    assert "registerMcpServer(" in src, (
        "src/index.ts no longer calls pi.registerMcpServer; installing the package "
        "would give pi the skills but no mariadb server"
    )
    assert 'MCP_SERVER_NAME = "mariadb"' in src, "the registered server is not named 'mariadb'"
    for launcher in ("mariadb-mcp-launcher.sh", "mariadb-mcp-launcher.cmd"):
        assert launcher in src, f"src/index.ts does not point at scripts/{launcher}"


def test_extension_is_a_default_export_factory():
    """pi loads the extension by calling its default export with the API object."""
    src = (skills.PLUGIN_ROOT / "src" / "index.ts").read_text(encoding="utf-8")
    assert "export default" in src, (
        "src/index.ts has no default export; pi would load the file and register nothing"
    )


@pytest.mark.parametrize(
    "script",
    ["mariadb-mcp-launcher.sh", "mariadb-mcp-launcher.cmd"],
)
def test_shipped_scripts_are_present(script: str):
    path = skills.PLUGIN_ROOT / "scripts" / script
    assert path.is_file(), f"missing {path.relative_to(skills.REPO_ROOT)}"
    if script.endswith(".sh"):
        import os

        assert os.access(path, os.X_OK), f"{script} is not executable"
