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

"""Shared parsing layer for the MariaDB plugin skill tests.

Reads the vendored skills under ``hermes/dev-plugin/skills`` and their manifest, splits
SKILL.md frontmatter from body, and extracts the bits the tests assert on
(sections, ```sql fences, See Also cross-references).

Pure stdlib + PyYAML so it works in the static tier with no DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

# Repo layout: <repo>/hermes/dev-plugin-tests/lib/skills.py
# parents[1] is the tests root, whose sibling "dev-plugin" is the plugin.
TESTS_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = TESTS_ROOT.parent / "dev-plugin"
REPO_ROOT = TESTS_ROOT.parents[1]
SKILLS_ROOT = PLUGIN_ROOT / "skills"
MANIFEST_PATH = SKILLS_ROOT / ".skills-manifest.json"

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
_SQL_FENCE_RE = re.compile(r"```sql\n(.*?)```", re.DOTALL)
# Any fenced block opener, used to check fences are balanced.
_FENCE_RE = re.compile(r"^```", re.MULTILINE)
# A `mariadb-...` / `mysql-...` skill name cross-referenced in inline code.
# The backticks matter: skills always reference each other in code spans (e.g.
# `mariadb-dump`), whereas the same token often appears bare inside a
# mariadb.com/docs URL path (…/mariadb-binlog-options, …/mariadb-command-line-client)
# — those are documentation slugs, not skills, and must not count as references.
_SKILL_REF_RE = re.compile(r"`((?:mariadb|mysql)-[a-z0-9-]+)`")


@dataclass
class Skill:
    """One vendored skill (a directory containing SKILL.md)."""

    name: str
    path: Path  # absolute path to SKILL.md
    layer: str  # manifest layer key, e.g. "granular-statements"
    rel_path: str  # path as recorded in the manifest
    frontmatter: dict = field(default_factory=dict)
    body: str = ""

    @property
    def dir_name(self) -> str:
        return self.path.parent.name

    @property
    def is_statement(self) -> bool:
        return self.layer == "granular-statements"

    def sql_blocks(self) -> list[str]:
        """Every ```sql fenced block body, in document order."""
        return [m.strip() for m in _SQL_FENCE_RE.findall(self.body)]

    def fence_count(self) -> int:
        return len(_FENCE_RE.findall(self.raw_text()))

    def raw_text(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def see_also_refs(self) -> set[str]:
        """Skill names referenced under a 'See Also' heading."""
        section = _section(self.body, "See Also")
        if not section:
            return set()
        refs = set(_SKILL_REF_RE.findall(section))
        refs.discard(self.name)  # never count a self-reference
        return refs


def _split_frontmatter(text: str) -> tuple[dict, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    data = yaml.safe_load(m.group(1)) or {}
    if not isinstance(data, dict):
        data = {}
    return data, m.group(2)


def _section(body: str, heading: str) -> str:
    """Return the markdown under a `## heading` up to the next same-level heading."""
    pattern = re.compile(
        rf"^#{{1,6}}\s+{re.escape(heading)}\s*$(.*?)(?=^#{{1,6}}\s|\Z)",
        re.DOTALL | re.MULTILINE | re.IGNORECASE,
    )
    m = pattern.search(body)
    return m.group(1) if m else ""


def has_section(body: str, heading: str) -> bool:
    return bool(_section(body, heading))


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    import json

    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_skills() -> tuple[Skill, ...]:
    """All skills listed in the manifest, with frontmatter/body parsed."""
    manifest = load_manifest()
    skills: list[Skill] = []
    for layer_key, layer in manifest.get("layers", {}).items():
        for entry in layer.get("skills", []):
            md_path = SKILLS_ROOT / entry["path"]
            fm, body = ({}, "")
            if md_path.is_file():
                fm, body = _split_frontmatter(md_path.read_text(encoding="utf-8"))
            skills.append(
                Skill(
                    name=entry["name"],
                    path=md_path,
                    layer=layer_key,
                    rel_path=entry["path"],
                    frontmatter=fm,
                    body=body,
                )
            )
    return tuple(skills)


def statement_skills() -> list[Skill]:
    return [s for s in load_skills() if s.is_statement]


def skill_names() -> set[str]:
    return {s.name for s in load_skills()}

def additional_skills() -> list[Skill]:
    """The skills vendored from this repo's own ``additional-skills/`` tree."""
    return [s for s in load_skills() if s.layer == "additional"]


def additional_sources(name: str) -> list[Path]:
    """Every ``additional-skills/<subfolder>/<name>/SKILL.md`` matching a skill name.

    The manifest records the layer (``additional``) but not which subfolder
    (``sql``/``rest``/``schema-management``) a skill came from, so the source is
    found by name. A list is returned rather than a single path because two
    subfolders holding the same skill name is itself a fault worth reporting.
    """
    return sorted((REPO_ROOT / "additional-skills").glob(f"*/{name}/SKILL.md"))


def discover_disk_skills() -> list[Path]:
    """Every SKILL.md actually present under the plugin's skills/ (manifest-independent)."""
    return sorted(SKILLS_ROOT.rglob("SKILL.md"))
