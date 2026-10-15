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

"""Tier 2 — the connection `sandbox.deploy` registers, and `db.connect` on it.

This covers the one path an agent actually takes and that nothing else here
exercised. Every other tier reaches the database with credentials it was already
given: the rest of the db tier connects with PyMySQL straight from
``instance.dsn``, and the e2e modules pass host/port/user/password on each SQL
tool call or hand the model the password in the prompt. So a green suite proved a
sandbox was *running*, never that an agent could reach it the way the README
promises — deploy an instance, then connect with no credentials at all.

What makes that work is a chain of three things in the shell's ``mcp_plugin``,
none of which is obvious from the outside:

* ``sandbox.deploy`` calls ``config.store_connection("root@127.0.0.1:<port>",
  password)``, whose only effect is to write that password into the shell's
  secret store.
* ``db.list_connections`` is *derived from those secrets* — it lists the URIs
  that have a stored password, rather than a connection registry of its own.
* ``db.connect`` checks its argument against that same list and refuses anything
  absent from it with "is not a configured connection".

So the registration is only visible through the config home that holds the secret
store — hence ``sandbox.mcp_client``, which reuses the instance's — and an
unreadable secret store makes *every* connection look unconfigured. That last
failure mode is not hypothetical: on Windows over SSH the credential helper is
unavailable and ``db.list_connections`` fails outright, which reads exactly like
a deploy that never registered anything.

The URI no longer has to be spelled the way it is stored: ``db.connect`` now
normalizes a scheme prefix, host case, the default port and an inline password,
while keeping anything the configured connection does not name — a default
schema, a connection option — significant. Both halves are pinned below, because
each protects something: the first that a client composing its own URI is
understood, the second that ``ssl-mode=REQUIRED`` cannot be silently dropped by
answering with the plain connection instead.
"""

from __future__ import annotations

import pytest

from lib import sandbox

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def instance(mariadb_sandbox):
    """The deployed sandbox, or a skip when the tier is on an explicit server."""
    if mariadb_sandbox is None:
        pytest.skip(
            "the db tier is pointed at an already-running server via MARIADB_*, "
            "so no sandbox was deployed and no connection was registered"
        )
    return mariadb_sandbox


def _tools(client) -> set:
    return {tool.get("name") for tool in client.list_tools()}


def test_deploy_registered_the_sandbox_connection(instance):
    """`sandbox.deploy` must leave the instance in `db.list_connections`.

    Asserted through the MCP server rather than by reading the secret store, so
    this fails the same way an agent would experience it.
    """
    uri = sandbox.connection_uri(instance)
    with sandbox.mcp_client(instance) as client:
        assert "db.list_connections" in _tools(client), (
            "the MCP server exposes no db.list_connections tool"
        )
        result = client.call_tool("db.list_connections", {})

    assert not sandbox.tool_failed(result), (
        "db.list_connections failed — on a host whose credential helper is "
        f"unavailable this is what a missing registration looks like: "
        f"{sandbox.tool_text(result)}"
    )
    assert uri in sandbox.tool_text(result), (
        f"{uri!r} is not among the configured connections after sandbox.deploy, "
        f"so an agent would have to be told the password. Got: "
        f"{sandbox.tool_text(result)}"
    )


def test_connect_opens_it_without_being_given_credentials(instance):
    """The point of the registration: `db.connect(uri)` and nothing else.

    No password is passed here — if this passes, `sandbox.deploy` really did
    leave a usable connection behind, which is what the README claims.
    """
    uri = sandbox.connection_uri(instance)
    with sandbox.mcp_client(instance) as client:
        opened = client.call_tool("db.connect", {"uri": uri})
        assert not sandbox.tool_failed(opened), (
            f"db.connect({uri!r}) failed: {sandbox.tool_text(opened)}"
        )
        connection_id = sandbox.tool_text(opened).strip()
        assert connection_id, "db.connect returned no connection id"

        try:
            # Prove the handle actually works, not merely that one was minted.
            ran = client.call_tool(
                "db.execute_sql",
                {"connection_id": connection_id, "sql": "SELECT 1 AS one"},
            )
            assert not sandbox.tool_failed(ran), (
                f"db.execute_sql on the registered connection failed: "
                f"{sandbox.tool_text(ran)}"
            )
            assert "1" in sandbox.tool_text(ran), (
                f"SELECT 1 returned nothing usable: {sandbox.tool_text(ran)}"
            )
        finally:
            client.call_tool("db.close", {"connection_id": connection_id})


def test_connect_accepts_other_spellings_of_the_same_connection(instance):
    """A client that composes the URI itself must still be understood.

    `db.list_connections` hands out the bare `user@host:port`, but a client
    writing a URI tends to prefix a scheme, case the host differently or put a
    password in it. `config.normalize_connection_uri` folds exactly those
    together — the `mariadb://` scheme, host case, default port, an inline
    password — because the alternative is telling a caller that a connection it
    can see listed is not configured.

    Note this is a *behaviour change*: these spellings used to be rejected, and
    the project's notes recorded the bare form as mandatory. They are equivalent
    now, and this pins that.
    """
    uri = sandbox.connection_uri(instance)
    spellings = [
        f"mariadb://{uri}",
        f"{instance.user}:wrong-password-ignored@{instance.host}:{instance.port}",
        f"{instance.user}@{instance.host.upper()}:{instance.port}",
    ]

    with sandbox.mcp_client(instance) as client:
        for spelling in spellings:
            opened = client.call_tool("db.connect", {"uri": spelling})
            assert not sandbox.tool_failed(opened), (
                f"db.connect({spelling!r}) was refused, but it names the same "
                f"connection as {uri!r}: {sandbox.tool_text(opened)}"
            )
            connection_id = sandbox.tool_text(opened).strip()
            # Close each one: only a limited number may be open at a time.
            client.call_tool("db.close", {"connection_id": connection_id})


def test_connect_refuses_the_mysql_scheme(instance):
    """`mariadb://` is the scheme; `mysql://` no longer names the same connection.

    The shell used to fold `mysql://` in with the other spellings. Since
    `mariadb://` became the default scheme it is refused, and a caller that
    composes a `mysql://` URI is told the connection is not configured.
    """
    spelling = f"mysql://{sandbox.connection_uri(instance)}"
    with sandbox.mcp_client(instance) as client:
        result = client.call_tool("db.connect", {"uri": spelling})
        assert sandbox.tool_failed(result), (
            f"db.connect({spelling!r}) succeeded, but mysql:// is no longer an "
            "accepted scheme"
        )
        assert "not a configured connection" in sandbox.tool_text(result).lower(), (
            f"the refusal should say the URI is not a configured connection. Got: "
            f"{sandbox.tool_text(result)}"
        )


def test_connect_refuses_a_uri_that_asks_for_more_than_was_configured(instance):
    """A URI naming something extra is a *different* connection, and must fail.

    The normalizer folds only spellings that mean the same thing. A default
    schema or a connection option is kept and has to match, deliberately: the
    alternative is handing back a connection that quietly does not do what was
    asked — `ssl-mode=REQUIRED` being the case that matters.
    """
    uri = sandbox.connection_uri(instance)
    extras = [f"{uri}/some_schema", f"{uri}?ssl-mode=REQUIRED"]

    with sandbox.mcp_client(instance) as client:
        for extra in extras:
            result = client.call_tool("db.connect", {"uri": extra})
            assert sandbox.tool_failed(result), (
                f"db.connect({extra!r}) succeeded, but it asks for more than the "
                "configured connection provides, so it must not be silently "
                "answered with the plain one"
            )
            assert "not a configured connection" in sandbox.tool_text(result).lower(), (
                "the refusal should say the URI is not a configured connection, "
                "so the caller knows to check db.list_connections. Got: "
                f"{sandbox.tool_text(result)}"
            )
