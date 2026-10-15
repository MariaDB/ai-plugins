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

"""A tiny MCP stdio client — just enough to call a handful of tools.

Speaks JSON-RPC 2.0 over newline-delimited stdio, which is the framing the
mariadb-shell MCP server uses when launched as

    mariadb-shell -- mcp start-server --transport=stdio

(i.e. exactly what ``scripts/mariadb-mcp-launcher.sh`` execs). Used by the db
tier to deploy and tear down the throwaway sandbox instance it runs against (see
``lib/sandbox.py``) and, where there is an e2e tier, to tear its sandbox down
through a real ``sandbox.delete`` call and to discover a tool's exact
name/argument schema at runtime (the server is the authority — we don't hardcode
a guess).

This is intentionally minimal: one request in flight at a time, no batching,
generous timeouts, best-effort cleanup. It is a test helper, not a client lib.
Two things it does take care of, because both cost a hung test run otherwise:
a server-initiated request (an elicitation, say) is answered with an error
instead of being ignored, and the subprocess is never left behind when the
handshake fails.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from typing import IO, Any


class MCPStdioError(RuntimeError):
    pass


class MCPStdioClient:
    """Spawn an MCP server over stdio and issue a handful of requests to it."""

    def __init__(self, command: list[str], env: dict | None = None, timeout: float = 30.0):
        self._command = command
        self._env = env
        self._timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._stderr: IO[str] | None = None
        self._next_id = 0

    # -- lifecycle -----------------------------------------------------------
    def __enter__(self) -> "MCPStdioClient":
        # stderr goes to a temp file rather than a pipe: a pipe nobody drains
        # can fill up and block the server, and DEVNULL would throw away the
        # message that explains a failed start (a missing plugin, say).
        self._stderr = tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace")
        self._proc = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr,
            env=self._env,
            text=True,
            bufsize=1,
        )
        try:
            self._initialize()
        except BaseException:
            self.__exit__()  # never leak the shell subprocess
            raise
        return self

    def __exit__(self, *exc) -> None:
        proc, self._proc = self._proc, None
        stderr, self._stderr = self._stderr, None
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    pass
        if stderr is not None:
            stderr.close()

    # -- diagnostics ---------------------------------------------------------
    def stderr_text(self, limit: int = 2000) -> str:
        """What the server wrote to stderr so far — for failure messages."""
        if self._stderr is None:
            return ""
        try:
            self._stderr.seek(0)
            return self._stderr.read()[-limit:].strip()
        except Exception:
            return ""

    # -- JSON-RPC plumbing ---------------------------------------------------
    def _send(self, payload: dict) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

    def _read_result(self, expected_id: int) -> Any:
        assert self._proc and self._proc.stdout
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            line = self._proc.stdout.readline()
            if line == "":
                raise MCPStdioError(
                    "MCP server closed the stream before responding"
                    + (f"; stderr: {self.stderr_text()}" if self.stderr_text() else "")
                )
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue  # ignore any non-JSON log noise on stdout
            # A server-initiated request (e.g. elicitation/create, which the
            # path-gated tools fall back to). We can't answer it, but we must
            # say so — leaving it unanswered hangs the server, and us with it.
            if msg.get("method") and msg.get("id") is not None:
                self._send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "error": {
                            "code": -32601,
                            "message": "this client cannot answer server requests",
                        },
                    }
                )
                continue
            if msg.get("id") != expected_id:
                continue  # a notification or an unrelated response
            if "error" in msg:
                raise MCPStdioError(f"MCP error: {msg['error']}")
            return msg.get("result")
        raise MCPStdioError(f"timed out waiting {self._timeout}s for response id={expected_id}")

    def _request(self, method: str, params: dict | None = None) -> Any:
        self._next_id += 1
        rid = self._next_id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        return self._read_result(rid)

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ai-plugins-tests", "version": "0"},
            },
        )
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # -- high level ----------------------------------------------------------
    def list_tools(self) -> list[dict]:
        result = self._request("tools/list") or {}
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> Any:
        return self._request("tools/call", {"name": name, "arguments": arguments})
