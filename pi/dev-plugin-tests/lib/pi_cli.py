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

"""Driving the real ``pi`` CLI for the tier-4 e2e test.

How pi has to be wired differs from Claude Code and Codex in ways that are worth
stating, because each one is a way the tier can silently test nothing:

* **A project-local install, honoured only with ``--approve``.** ``pi install -l``
  writes the package into ``.pi/settings.json`` in the current directory, which
  keeps a run hermetic — nothing lands in the user's own pi configuration. But pi
  ignores project-local files unless the run passes ``-a``/``--approve``, so
  without it the package is configured and never loaded. (``pi list`` reads only
  the user settings, so it reports "No packages installed" either way — it is not
  a check that the project-local package is live.)

* **Skills come from the package, as with Codex.** There is no project directory
  pi scans for skills; the repo-root ``package.json`` ``pi`` field is what
  declares them, so installing the repo *is* how the skills reach the model.

* **A throwaway agent dir, so the user's own packages stay out.** A globally
  installed ``pi-mcp-adapter`` replaces Pi's built-in MCP (and Pi then writes
  ``-builtin:mcp`` into the user's settings), which would silently drop the server
  this package registers. ``isolated_agent_dir`` copies only the provider files
  (auth, models, default model) into a temp ``PI_CODING_AGENT_DIR``.

* **The provider is whatever pi is configured for**, including a local one. There
  is no API key for this suite to check, which is why the prerequisite gate runs
  a trivial prompt rather than inspecting credentials: ``pi auth check`` reports
  ``not_ready`` even when runs succeed against a working provider.

* **Evidence is the JSONL stream from ``--mode json``**, whose events are
  ``{"type": "message_start"|"message_end"|"message_update", "message": {...}}``.
  Assistant text is assembled from those rather than from the plain-text output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = TESTS_ROOT.parent / "dev-plugin"
REPO_ROOT = TESTS_ROOT.parents[1]

# The MCP server name src/index.ts registers with Pi's built-in MCP.
SERVER_NAME = "mariadb"

# Provider files copied into the isolated agent dir; everything else (packages,
# extensions, mcp.json, sessions) is left behind on purpose.
_PROVIDER_FILES = ("auth.json", "models.json", "models-store.json")
_SETTINGS_KEPT = ("defaultProvider", "defaultModel", "defaultThinkingLevel", "enabledModels")


def pi_bin() -> str:
    return os.environ.get("PI_BIN") or shutil.which("pi") or ""


def missing_prerequisite() -> str | None:
    """Why the e2e tier cannot run here, or None when it can."""
    if not pi_bin():
        return "pi CLI not found (set PI_BIN or add it to PATH)"
    if not (REPO_ROOT / "package.json").is_file():
        return f"no pi manifest at {REPO_ROOT / 'package.json'}"
    return None


def isolated_agent_dir(target: Path) -> Path:
    """A PI_CODING_AGENT_DIR holding only the user's provider setup."""
    source = Path(os.environ.get("PI_CODING_AGENT_DIR") or Path.home() / ".pi" / "agent")
    target.mkdir(parents=True, exist_ok=True)
    for name in _PROVIDER_FILES:
        if (source / name).is_file():
            shutil.copy2(source / name, target / name)
    settings = {}
    if (source / "settings.json").is_file():
        try:
            settings = json.loads((source / "settings.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    kept = {k: v for k, v in settings.items() if k in _SETTINGS_KEPT}
    (target / "settings.json").write_text(json.dumps(kept, indent=2), encoding="utf-8")
    return target


def provider_ready(timeout: int = 120, env: dict | None = None) -> str | None:
    """Run a trivial prompt; return None when pi can reach a model, else why not.

    Credentials cannot be checked directly: pi resolves a provider from its own
    config (which may be a local model needing no key at all) and `pi auth check`
    reports `not_ready` even when runs work. The only honest test is a round trip.
    """
    try:
        proc = subprocess.run(
            [pi_bin(), "-p", "--no-session", "Reply with exactly: READY"],
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return f"pi did not answer a trivial prompt within {timeout}s"
    if proc.returncode != 0 or "READY" not in proc.stdout:
        detail = (proc.stderr or proc.stdout or "").strip()[-300:]
        return f"pi cannot reach a model provider: {detail or 'no output'}"
    return None


def install_package(
    project: Path, source: Path | None = None, env: dict | None = None
) -> subprocess.CompletedProcess:
    """Install this repo as a pi package, project-locally (`.pi/settings.json`)."""
    return subprocess.run(
        [pi_bin(), "install", "-l", "--approve", str(source or REPO_ROOT)],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=180,
        stdin=subprocess.DEVNULL,
        env=env,
    )


@dataclass
class PiRun:
    """One `pi -p` invocation: raw streams plus the parsed JSONL events."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    events: list[dict] = field(default_factory=list)

    @property
    def diagnostics(self) -> str:
        if self.timed_out:
            return "\npi did not finish within the timeout"
        return (
            f"\n--- pi stderr ---\n{self.stderr[-2000:]}"
            f"\n--- assistant text ---\n{self.assistant_text()[-2000:]}"
        )

    def assistant_text(self) -> str:
        """All assistant text in the run, concatenated.

        Assembled from the message events rather than taken from stdout so it is
        the model's actual output, not whatever the renderer chose to show.
        """
        parts: list[str] = []
        for event in self.events:
            message = event.get("message") or {}
            if message.get("role") != "assistant":
                continue
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    parts.append(block["text"])
        if not parts:  # text mode, or a renderer that emitted nothing structured
            return self.stdout
        return "\n".join(dict.fromkeys(parts))  # de-dup: message_update repeats partials

    def mcp_tool_results(self, server: str = SERVER_NAME) -> list[dict]:
        """The finished calls of `server`'s MCP tools, direct or from codemode.

        Pi reports each one as a `tool_execution_end` event whose result details
        name the server, so this is the server answering — not the model saying so.
        """
        return [
            event
            for event in self.events
            if event.get("type") == "tool_execution_end"
            and ((event.get("result") or {}).get("details") or {}).get("server") == server
        ]

    def model(self) -> str:
        for event in self.events:
            message = event.get("message") or {}
            if message.get("model"):
                return f"{message.get('provider', '?')}/{message['model']}"
        return "unknown"


def run_pi(prompt: str, *, project: Path, timeout: int, extra_env: dict | None = None) -> PiRun:
    """Run `pi -p` once in `project`, with the project-local package trusted.

    ``--approve`` is what makes the project-local install take effect, and
    ``--no-session`` keeps the run from leaving session files behind.
    """
    env = dict(os.environ)
    env.update(extra_env or {})

    cmd = [
        pi_bin(),
        "-p",
        "--approve",
        "--no-session",
        "--mode", "json",
        prompt,
    ]
    run = PiRun()
    try:
        proc = subprocess.run(
            cmd,
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired as exc:
        run.timed_out = True
        run.stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode()
        run.stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode()
    else:
        run.returncode, run.stdout, run.stderr = proc.returncode, proc.stdout, proc.stderr

    for line in run.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            run.events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return run
