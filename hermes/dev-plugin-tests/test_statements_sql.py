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

"""Tier 2 — execute the skills' recommended SQL against a live MariaDB 11.8.

Each golden-fixture case (fixtures/<skill>.yaml) becomes its own
parametrized test, so a failure points straight at the skill claim it verifies.
The server comes from the `mariadb_connection` fixture, which deploys a
throwaway sandbox instance unless MARIADB_* names one that is already running
(see conftest.py and lib/sandbox.py).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import yaml

from lib import skills

pytestmark = pytest.mark.db

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_cases():
    """Flatten every fixture file into (skill, case) pairs with stable ids."""
    items, ids = [], []
    for path in sorted(FIXTURES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        skill = data.get("skill", path.stem)
        for case in data.get("cases") or []:
            items.append((skill, case))
            ids.append(f"{skill}::{case['name']}")
    return items, ids


_CASES, _IDS = _load_cases()


def test_every_fixture_targets_a_real_statement_skill():
    """Guard: fixture files must map to actual statement skills (catches typos/renames)."""
    statement_names = {s.name for s in skills.statement_skills()}
    fixture_skills = {p.stem for p in FIXTURES_DIR.glob("*.yaml")}
    unknown = fixture_skills - statement_names
    assert not unknown, f"fixture files without a matching statement skill: {sorted(unknown)}"


def _check_assert(cur, a: dict, ns: str):
    cur.execute(a["query"].replace("{ns}", ns))
    rows = cur.fetchall()
    if "rowcount" in a:
        assert len(rows) == a["rowcount"], f"expected {a['rowcount']} rows, got {len(rows)}"
    if "rowcount_min" in a:
        assert len(rows) >= a["rowcount_min"], f"expected >= {a['rowcount_min']} rows, got {len(rows)}"
    if "equals" in a or "contains" in a:
        col = a.get("column", 0)
        actual = rows[0][col] if rows else None
        if "equals" in a:
            assert str(actual).strip() == str(a["equals"]).strip(), (
                f"query {a['query']!r}: expected {a['equals']!r}, got {actual!r}"
            )
        if "contains" in a:
            assert a["contains"] in str(actual), (
                f"query {a['query']!r}: {a['contains']!r} not in {actual!r}"
            )


@pytest.mark.skipif(not _CASES, reason="no golden fixtures defined yet")
@pytest.mark.parametrize(("skill", "case"), _CASES, ids=_IDS)
def test_sql_case(mariadb_connection, skill, case):
    import pymysql

    ns = "skilltest_" + uuid.uuid4().hex[:12]
    sub = lambda s: s.replace("{ns}", ns)
    conn = mariadb_connection

    with conn.cursor() as cur:
        cur.execute(f"CREATE DATABASE `{ns}`")
        cur.execute(f"USE `{ns}`")
        try:
            for stmt in case.get("setup", []):
                cur.execute(sub(stmt))

            statements = [sub(s) for s in case["sql"]]
            expect = case.get("expect", "success")

            if expect == "success":
                for s in statements:
                    cur.execute(s)
            else:
                # expect an error: all but the last must succeed, the last must raise.
                *head, last = statements
                for s in head:
                    cur.execute(s)
                with pytest.raises(pymysql.MySQLError) as exc_info:
                    cur.execute(last)
                if isinstance(expect, dict) and "error" in expect:
                    assert exc_info.value.args[0] == expect["error"], (
                        f"expected errno {expect['error']}, got {exc_info.value.args[0]}"
                    )

            for a in case.get("assert", []):
                _check_assert(cur, a, ns)
        finally:
            cur.execute(f"SHOW DATABASES LIKE '{ns}%'")
            for (dbname,) in cur.fetchall():
                cur.execute(f"DROP DATABASE IF EXISTS `{dbname}`")
