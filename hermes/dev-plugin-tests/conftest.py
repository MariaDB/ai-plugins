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

"""Shared pytest fixtures.

Makes ``lib`` importable and provides the live-MariaDB connection used by the
``db`` tier. By default that server is a throwaway **sandbox instance** this
suite deploys itself through the mariadb-shell MCP server (see
``lib/sandbox.py``), so the tier needs nothing running beforehand. Pointing any
``MARIADB_*`` variable at an existing server (CI's service container,
``docker-compose.yml``) uses that instead.

The static tier needs none of the DB machinery, so both PyMySQL and the sandbox
are only touched from inside the fixtures.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

# Make `from lib import skills` work regardless of where pytest is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The variables that name an already-running server. Any of them switches the
# db tier off the sandbox and onto that server.
_SERVER_ENV_VARS = ("MARIADB_HOST", "MARIADB_PORT", "MARIADB_USER", "MARIADB_PASSWORD")


def _explicit_server() -> dict | None:
    """The connection to a pre-existing server, or None to use a sandbox."""
    if not any(os.environ.get(var) for var in _SERVER_ENV_VARS):
        return None
    return {
        "host": os.environ.get("MARIADB_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MARIADB_PORT", "3306")),
        "user": os.environ.get("MARIADB_USER", "root"),
        "password": os.environ.get("MARIADB_PASSWORD", "test"),
    }


@pytest.fixture(scope="session")
def mariadb_sandbox():
    """The sandbox instance the db tier deployed, or None for an explicit server.

    Split out from :func:`mariadb_server` so that one deploy serves both: tests
    that only need a connection take ``mariadb_server``, while tests that need
    the instance itself — its port, or the shell config home whose secret store
    holds the connection `sandbox.deploy` registered — take this.

    Yields:
        A ``lib.sandbox.SandboxInstance``, or None when ``MARIADB_*`` named a
        server that was already running (nothing was deployed, so there is no
        instance and no registered connection).
    """
    if _explicit_server() is not None:
        yield None
        return

    from lib import sandbox

    try:
        with sandbox.deployed_sandbox() as instance:
            yield instance
    except sandbox.SandboxUnavailable as exc:
        pytest.skip(
            f"cannot deploy a MariaDB sandbox for the db tier ({exc}); "
            f"or point {'/'.join(_SERVER_ENV_VARS)} at a running server"
        )


@pytest.fixture(scope="session")
def mariadb_server(mariadb_sandbox):
    """The MariaDB the db tier runs against, for the whole session.

    A sandbox instance is deployed on a free port and deleted afterwards, unless
    ``MARIADB_*`` points at a server that is already running. Skips the tier when
    no sandbox can be deployed (no mariadb-shell, no server binary, an MCP server
    without the sandbox tools) — a deploy that fails outright is an error.

    Yields:
        A dict with the PyMySQL connect() kwargs plus ``explicit``, which says
        whether the server was handed to us or deployed here.
    """
    explicit = _explicit_server()
    if explicit is not None:
        yield {**explicit, "explicit": True}
        return

    yield {**mariadb_sandbox.dsn, "explicit": False}


@pytest.fixture(scope="session")
def mariadb_connection(mariadb_server):
    """A session-scoped connection to the test MariaDB server.

    Skips the tier if PyMySQL is missing, or if a server that was configured
    externally turns out to be unreachable. A sandbox we just deployed and can't
    reach is a failure, not a skip.
    """
    try:
        import pymysql
    except ImportError:
        pytest.skip("PyMySQL not installed — skipping the live-DB tier")

    dsn = {k: v for k, v in mariadb_server.items() if k != "explicit"}
    try:
        conn = pymysql.connect(
            autocommit=True,
            charset="utf8mb4",
            **dsn,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        if not mariadb_server["explicit"]:
            raise
        pytest.skip(
            f"MariaDB unreachable at {dsn['host']}:{dsn['port']} ({exc}); "
            "unset the MARIADB_* variables to use a sandbox instead, or start "
            "the docker-compose service"
        )
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def scratch_db(mariadb_connection):
    """A throwaway database, dropped after the test, for isolation.

    Yields the open connection with the scratch database selected as default.
    """
    name = "skilltest_" + uuid.uuid4().hex[:12]
    with mariadb_connection.cursor() as cur:
        cur.execute(f"CREATE DATABASE `{name}`")
        cur.execute(f"USE `{name}`")
    try:
        yield mariadb_connection, name
    finally:
        with mariadb_connection.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
