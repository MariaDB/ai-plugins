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

"""Provision the throwaway MariaDB instance the db tier runs against.

The db tier used to need a server someone had already started (docker-compose,
or CI's service container) and skipped itself when 127.0.0.1:3306 refused the
connection. It now deploys its own **sandbox instance** instead, the same way
mysql-shell-plugins/mcp_plugin/tests does: through the mariadb-shell MCP server's
`sandbox.*` tools, driven over stdio (see ``lib/mcp_stdio.py``). The instance is
deployed on a free ephemeral port, used by the tests, then stopped and deleted.

Two details make this work headlessly:

* **The shell's user config home is isolated** — a temp dir handed to the server
  via MYSQLSH_USER_CONFIG_HOME. It gives us a settings.json we own (see below)
  and a throwaway secret store for the connection `sandbox.deploy` registers, so
  the run never touches the developer's real `~/.mariadb-shell`. The shell loads
  its plugins from that config home, so whatever plugins the real one has are
  symlinked into ours — without them the server has no `mcp` object at all.
* **The sandbox directory is allow-listed** — the MCP server's file-touching
  tools reject paths outside `allowedPaths` and fall back to an elicitation that
  a headless client can't answer, so a non-allowed path means a hung deploy, not
  an error. We write our own `plugin_data/mcp_plugin/settings.json` listing the
  temp sandbox dir before starting the server.

An absent toolchain (no mariadb-shell, no server binary, an MCP server without
the sandbox tools) raises :class:`SandboxUnavailable` and the db tier skips. A
deploy that *should* have worked and didn't is an error, not a skip.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import tempfile
from dataclasses import dataclass
from pathlib import Path

from lib.mcp_stdio import MCPStdioClient, MCPStdioError

# Root password for the sandbox. Must not be empty — a blank sandbox root
# password is rejected by the shell.
SANDBOX_PASSWORD = "skilltest_root"

# Deploying initializes a data directory and starts a server, so it gets a far
# more generous budget than an ordinary tool call.
DEPLOY_TIMEOUT = 300.0
TOOL_TIMEOUT = 120.0


class SandboxUnavailable(RuntimeError):
    """The toolchain needed to deploy a sandbox isn't there — skip, don't fail."""


@dataclass(frozen=True)
class SandboxInstance:
    """Where the deployed instance is and how to connect to it."""

    host: str
    port: int
    user: str
    password: str
    sandbox_dir: Path
    config_home: Path

    @property
    def dsn(self) -> dict:
        """Keyword arguments for a PyMySQL connect() call."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
        }


def shell_binary() -> str | None:
    """The mariadb-shell to drive, or None when there isn't one.

    MARIADB_SHELL_BIN is what the e2e tier and the MCP launcher already use;
    MARIADB_SHELL is what run_tests.py and the mcp_plugin suite set.
    """
    return (
        os.environ.get("MARIADB_SHELL_BIN")
        or os.environ.get("MARIADB_SHELL")
        or shutil.which("mariadb-shell")
    )


def server_binary_available() -> bool:
    """Whether a server binary is on the PATH for the sandbox to start.

    The MCP server subprocess inherits our PATH, so this is a fair proxy.
    MARIADB_SANDBOX_MARIADBD names one explicitly (e.g. to pin the version the
    fixtures were written against).
    """
    if os.environ.get("MARIADB_SANDBOX_MARIADBD"):
        return True
    return bool(shutil.which("mariadbd") or shutil.which("mysqld"))


def find_free_port() -> int:
    """A currently-free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def real_config_home() -> Path | None:
    """The developer's own shell config home — only read, to find its plugins."""
    for var in ("MARIADB_SHELL_USER_CONFIG_HOME", "MYSQLSH_USER_CONFIG_HOME"):
        configured = os.environ.get(var)
        if configured:
            return Path(configured)
    for name in (".mariadb-shell", ".mysqlsh"):
        candidate = Path.home() / name
        if (candidate / "plugins").is_dir():
            return candidate
    return None


def _prepare_config_home(sandbox_dir: Path) -> Path:
    """Build an isolated shell config home that can deploy into `sandbox_dir`."""
    config_home = Path(tempfile.mkdtemp(prefix="skilltest_cfg_"))

    # The shell loads plugins from the config home, and on a source build the
    # `mcp` plugin is one of them, so carry over whatever the real one has.
    plugins = config_home / "plugins"
    plugins.mkdir()
    source = real_config_home()
    if source and (source / "plugins").is_dir():
        for entry in sorted((source / "plugins").iterdir()):
            target = entry.resolve()
            if target.is_dir():
                (plugins / entry.name).symlink_to(target, target_is_directory=True)

    settings = config_home / "plugin_data" / "mcp_plugin" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(
        json.dumps({"allowedPaths": [str(sandbox_dir)]}, indent=4), encoding="utf-8"
    )
    return config_home


def _server_env(config_home: Path) -> dict:
    env = dict(os.environ)
    # Both spellings: the fork still honours the MYSQLSH_ name, newer builds
    # also read the MARIADB_SHELL_ one.
    env["MYSQLSH_USER_CONFIG_HOME"] = str(config_home)
    env["MARIADB_SHELL_USER_CONFIG_HOME"] = str(config_home)
    env["MARIADB_SHELL_TERM_COLOR_MODE"] = "nocolor"
    return env


def _client(shell: str, env: dict, timeout: float) -> MCPStdioClient:
    return MCPStdioClient(
        # --quiet-start=2 keeps the shell banner off stdout, leaving only the
        # JSON-RPC stream.
        [shell, "--quiet-start=2", "--", "mcp", "start-server", "--transport=stdio"],
        env=env,
        timeout=timeout,
    )


def _payload_text(result: dict | None) -> str:
    """The text a tool returned, for error messages."""
    blocks = (result or {}).get("content") or []
    return " ".join(
        str(block.get("text", "")) for block in blocks if isinstance(block, dict)
    ).strip()


def _failed(result: dict | None) -> bool:
    return bool((result or {}).get("isError"))
# --------------------------------------------------------------------------- #
# Talking to the MCP server the instance was deployed through
# --------------------------------------------------------------------------- #
@contextlib.contextmanager
def mcp_client(instance: SandboxInstance, timeout: float = TOOL_TIMEOUT):
    """An MCP client on the *same* shell config home the instance was deployed with.

    Which config home is used is not incidental here. `sandbox.deploy` registers
    the instance as a configured connection by storing its password in the
    shell's secret store, and `db.list_connections` is derived from those
    secrets — so a client started against a different config home sees no
    connection at all, and `db.connect` reports the URI as unconfigured. Reusing
    ``instance.config_home`` is what makes the registration observable.
    """
    shell = shell_binary()
    if not shell:
        raise SandboxUnavailable(
            "mariadb-shell not found (set MARIADB_SHELL_BIN or put it on PATH)"
        )
    with _client(shell, _server_env(instance.config_home), timeout) as client:
        yield client


def tool_failed(result: dict | None) -> bool:
    """Whether a tool call came back as an error."""
    return _failed(result)


def tool_text(result: dict | None) -> str:
    """The text a tool returned, flattened — for assertions and messages."""
    return _payload_text(result)


def connection_uri(instance: SandboxInstance) -> str:
    """The URI `sandbox.deploy` registers for an instance.

    Mirrors `_sandbox_connection_uri` in the shell's mcp_plugin: bare
    ``user@host:port``, with no scheme. A ``mariadb://`` prefix does not match
    the stored key and is rejected as unconfigured.
    """
    return f"{instance.user}@{instance.host}:{instance.port}"


@contextlib.contextmanager
def deployed_sandbox(password: str = SANDBOX_PASSWORD):
    """Deploy a sandbox instance, yield it, then stop and delete it.

    Yields:
        A :class:`SandboxInstance`.

    Raises:
        SandboxUnavailable: when the toolchain to deploy one isn't present.
        MCPStdioError / RuntimeError: when a deploy that should have worked
            didn't — a real failure, not a reason to skip.
    """
    shell = shell_binary()
    if not shell:
        raise SandboxUnavailable(
            "mariadb-shell not found (set MARIADB_SHELL_BIN or put it on PATH)"
        )
    if not server_binary_available():
        raise SandboxUnavailable(
            "no mariadbd/mysqld on PATH for the sandbox to start "
            "(or set MARIADB_SANDBOX_MARIADBD)"
        )

    sandbox_dir = Path(tempfile.mkdtemp(prefix="skilltest_sbx_"))
    config_home = _prepare_config_home(sandbox_dir)
    env = _server_env(config_home)
    port = find_free_port()
    instance = SandboxInstance(
        host="127.0.0.1",
        port=port,
        user="root",
        password=password,
        sandbox_dir=sandbox_dir,
        config_home=config_home,
    )

    deployed = False
    try:
        try:
            with _client(shell, env, TOOL_TIMEOUT) as client:
                tools = {tool.get("name") for tool in client.list_tools()}
                if "sandbox.deploy" not in tools:
                    raise SandboxUnavailable(
                        "the mariadb-shell MCP server exposes no sandbox tools"
                    )
        except MCPStdioError as exc:
            # The server didn't even come up — most often a shell whose config
            # home has no mcp plugin. Not something the db tier can fix.
            raise SandboxUnavailable(f"cannot start the mariadb-shell MCP server: {exc}")

        arguments = {
            "port": port,
            "sandbox_dir": str(sandbox_dir),
            "password": password,
            # No TLS: a certificate would drag in openssl for an instance that
            # only ever serves localhost tests.
            "ssl": False,
        }
        mariadbd = os.environ.get("MARIADB_SANDBOX_MARIADBD")
        if mariadbd:
            arguments["mariadbd_path"] = mariadbd

        with _client(shell, env, DEPLOY_TIMEOUT) as client:
            result = client.call_tool("sandbox.deploy", arguments)
        if _failed(result):
            raise RuntimeError(
                f"sandbox.deploy failed on port {port}: {_payload_text(result)}"
            )
        deployed = True

        yield instance
    finally:
        if deployed:
            _destroy(shell, env, instance)
        shutil.rmtree(sandbox_dir, ignore_errors=True)
        shutil.rmtree(config_home, ignore_errors=True)


def _destroy(shell: str, env: dict, instance: SandboxInstance) -> None:
    """Stop and delete the instance, best effort — a leak outlives the run."""
    stopped = False
    try:
        with _client(shell, env, TOOL_TIMEOUT) as client:
            result = client.call_tool(
                "sandbox.stop",
                {
                    "port": instance.port,
                    "sandbox_dir": str(instance.sandbox_dir),
                    "password": instance.password,
                },
            )
            stopped = not _failed(result)
            if not stopped:
                # delete refuses a running instance, so force it down first.
                client.call_tool(
                    "sandbox.kill",
                    {"port": instance.port, "sandbox_dir": str(instance.sandbox_dir)},
                )
            client.call_tool(
                "sandbox.delete",
                {"port": instance.port, "sandbox_dir": str(instance.sandbox_dir)},
            )
    except Exception:  # noqa: BLE001 - teardown is best effort
        pass
