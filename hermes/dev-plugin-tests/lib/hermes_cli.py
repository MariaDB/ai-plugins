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

"""Driving the real ``hermes`` CLI for the tier-4 e2e test.

How Hermes has to be wired differs from the other harnesses in ways that are
worth stating, because each one is a way the tier can silently test nothing:

* **A throwaway profile, not a throwaway HERMES_HOME.** A fresh ``HERMES_HOME``
  makes Hermes provision a whole Python dependency environment for it from PyPI
  (minutes, and it fails offline). A *profile* (``hermes -p <name>``) gets its own
  home under ``<hermes home>/profiles/<name>`` — its own plugins, skills, config
  and sessions — but shares the install's environment. ``TemporaryProfile``
  creates one with ``--no-skills`` (so the only skills in it are the plugin's),
  copies the user's provider setup into it, and deletes it afterwards.

* **The user's own ``mcp_servers`` are dropped from the copied config.** A
  ``config.yaml`` server named ``mariadb`` *replaces* the plugin's server of that
  name, so a user who wired one up by hand would have the tier test their server
  instead of the plugin's.

* **The plugin is installed the way users install it**: ``hermes plugins install
  <git url>#hermes/dev-plugin``. The source is a throwaway git repository holding
  a copy of the working tree's plugin, so uncommitted changes are what gets tested.
  ``--enable`` because portable packages install disabled. No ``--force``: the
  install-time security scan blocks a *caution* verdict from a non-catalog source,
  and the plugin has to pass it the way users install it.

* **The provider is whatever Hermes is configured for.** There is no API key for
  this suite to check, so the prerequisite gate runs a trivial prompt.

* **Evidence is the JSONL stream from ``--format stream-json``**, whose events are
  ``{"type": "system"|"tool_use"|"tool_result"|"text"|"result", ...}``. MCP tools
  appear as ``mcp__<server>__<tool>``; plugin skills are loaded with
  ``skill_view`` under the namespace ``agent-plugin-<plugin>-<hash>:<skill>``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

TESTS_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = TESTS_ROOT.parent / "dev-plugin"
REPO_ROOT = TESTS_ROOT.parents[1]

# The plugin's name in plugin.json, and the server name in its mcp.json.
PLUGIN_NAME = "mariadb-dev"
SERVER_NAME = "mariadb"
# Prefix of the namespace Hermes gives the plugin's skills.
SKILL_NAMESPACE_PREFIX = f"agent-plugin-{PLUGIN_NAME}-"

# Provider setup copied into the temporary profile; everything else (plugins,
# skills, memories, sessions) is left behind on purpose.
_PROVIDER_FILES = ("auth.json", ".env")


def hermes_bin() -> str:
    return os.environ.get("HERMES_BIN") or shutil.which("hermes") or ""


def hermes_home() -> Path:
    """The Hermes home the user's own `hermes` runs against (the default profile)."""
    explicit = os.environ.get("HERMES_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", "").strip()
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "hermes"
    return Path.home() / ".hermes"


def missing_prerequisite() -> str | None:
    """Why the e2e tier cannot run here, or None when it can."""
    if not hermes_bin():
        return "hermes CLI not found (set HERMES_BIN or add it to PATH)"
    if not (hermes_home() / "config.yaml").is_file():
        return f"no Hermes config at {hermes_home() / 'config.yaml'} — run `hermes setup` first"
    if not (PLUGIN_ROOT / "plugin.json").is_file():
        return f"no plugin manifest at {PLUGIN_ROOT / 'plugin.json'}"
    return None


def _run(args: list[str], *, timeout: int, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [hermes_bin(), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
    )


class TemporaryProfile:
    """A Hermes profile that exists for the duration of a `with` block."""

    def __init__(self) -> None:
        # Profile names are lowercase alphanumeric.
        self.name = "mdbe2e" + uuid.uuid4().hex[:10]
        self.home = hermes_home() / "profiles" / self.name

    def __enter__(self) -> "TemporaryProfile":
        created = _run(["profile", "create", self.name, "--no-alias", "--no-skills"], timeout=120)
        if created.returncode != 0 or not self.home.is_dir():
            raise RuntimeError(
                f"`hermes profile create {self.name}` failed (exit {created.returncode}):\n"
                f"{created.stdout}\n{created.stderr}"
            )
        try:
            self._copy_provider_setup()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *exc) -> None:
        _run(["profile", "delete", "-y", self.name], timeout=120)
        shutil.rmtree(self.home, ignore_errors=True)

    def _copy_provider_setup(self) -> None:
        import yaml

        source = hermes_home()
        for name in _PROVIDER_FILES:
            if (source / name).is_file():
                shutil.copy2(source / name, self.home / name)
        config = yaml.safe_load((source / "config.yaml").read_text(encoding="utf-8")) or {}
        config.pop("mcp_servers", None)
        (self.home / "config.yaml").write_text(
            yaml.safe_dump(config, sort_keys=False), encoding="utf-8"
        )

    def hermes(self, *args: str, timeout: int = 300, cwd: Path | None = None) -> subprocess.CompletedProcess:
        """Run `hermes -p <this profile> <args…>`."""
        return _run(["-p", self.name, *args], timeout=timeout, cwd=cwd)

    def install_plugin(self, staging: Path, mcp_env: dict | None = None) -> subprocess.CompletedProcess:
        """Install the working tree's dev plugin the way users do, from a git URL.

        `staging` becomes a one-commit git repository with the plugin at the same
        subdirectory it has in this repo, so the install exercises the
        `<url>#hermes/dev-plugin` subdirectory form the README documents.
        `mcp_env` is merged into the staged mcp.json's `env`: Hermes passes an MCP
        server only that and a few safe variables, so this is how a test points the
        MCP launcher at a clean install directory.
        """
        target = staging / "hermes" / "dev-plugin"
        shutil.copytree(PLUGIN_ROOT, target, ignore=shutil.ignore_patterns(".DS_Store"))
        if mcp_env:
            mcp_json = target / "mcp.json"
            config = json.loads(mcp_json.read_text(encoding="utf-8"))
            config["mcpServers"][SERVER_NAME].setdefault("env", {}).update(mcp_env)
            mcp_json.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        for git_args in (
            ["init", "-q"],
            ["add", "-A"],
            ["-c", "user.email=e2e@localhost", "-c", "user.name=e2e", "commit", "-q", "-m", "plugin"],
        ):
            subprocess.run(["git", *git_args], cwd=staging, check=True, capture_output=True)
        return self.hermes(
            "plugins", "install", f"{staging.as_uri()}#hermes/dev-plugin", "--enable",
            timeout=300,
        )

    def installed_plugin_dir(self) -> Path:
        return self.home / "plugins" / PLUGIN_NAME


@dataclass
class HermesRun:
    """One `hermes chat -q` invocation: raw streams plus the parsed JSONL events."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    events: list[dict] = field(default_factory=list)

    @property
    def diagnostics(self) -> str:
        if self.timed_out:
            return "\nhermes did not finish within the timeout"
        calls = [f"{e.get('name')}({json.dumps(e.get('input'))[:120]})" for e in self.tool_uses()]
        return (
            f"\n--- tool calls ---\n" + "\n".join(calls[-30:])
            + f"\n--- hermes stderr ---\n{self.stderr[-2000:]}"
            + f"\n--- final text ---\n{self.final_text()[-2000:]}"
        )

    def tool_uses(self, name: str | None = None) -> list[dict]:
        return [
            e for e in self.events
            if e.get("type") == "tool_use" and (name is None or e.get("name") == name)
        ]

    def tool_results(self, name: str | None = None) -> list[dict]:
        return [
            e for e in self.events
            if e.get("type") == "tool_result" and (name is None or e.get("name") == name)
        ]

    def mcp_tool_results(self, server: str = SERVER_NAME) -> list[dict]:
        """Finished calls of `server`'s MCP tools — the server answering, not the model."""
        prefix = f"mcp__{server}__"
        return [e for e in self.tool_results() if str(e.get("name", "")).startswith(prefix)]

    def plugin_skills_viewed(self) -> list[str]:
        """Skills of this plugin the model loaded with `skill_view`, by bare name."""
        viewed = []
        for event in self.tool_uses("skill_view"):
            raw = json.dumps(event.get("input") or {})
            for token in raw.replace('"', " ").split():
                if token.startswith(SKILL_NAMESPACE_PREFIX) and ":" in token:
                    viewed.append(token.split(":", 1)[1].rstrip(",}"))
        return viewed

    def final_text(self) -> str:
        for event in reversed(self.events):
            if event.get("type") == "result":
                return str(event.get("text") or "")
        text = "".join(str(e.get("text", "")) for e in self.events if e.get("type") == "text")
        return text or self.stdout

    def model(self) -> str:
        for event in self.events:
            if event.get("type") == "system" and event.get("model"):
                return str(event["model"])
        return "unknown"


def run_hermes(profile: TemporaryProfile, prompt: str, *, project: Path, timeout: int,
               max_turns: int = 30, env: dict | None = None) -> HermesRun:
    """Run one single-query `hermes chat` in `project` against the temporary profile.

    ``--yolo`` because there is nobody to approve terminal or file actions in a
    test, and ``--in`` so file tools resolve against the project directory.
    ``env`` replaces the inherited environment of the hermes process.
    """
    cmd = [
        hermes_bin(), "-p", profile.name, "chat",
        "-q", prompt,
        "--format", "stream-json",
        "--yolo",
        "--max-turns", str(max_turns),
        "--in", str(project),
    ]
    run = HermesRun()
    try:
        proc = subprocess.run(
            cmd,
            cwd=project,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=env,
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


def provider_ready(profile: TemporaryProfile, project: Path, timeout: int = 300) -> str | None:
    """Run a trivial prompt; return None when Hermes can reach a model, else why not."""
    run = run_hermes(profile, "Reply with exactly: READY", project=project, timeout=timeout,
                     max_turns=2)
    if run.timed_out:
        return f"hermes did not answer a trivial prompt within {timeout}s"
    if run.returncode != 0 or "READY" not in run.final_text():
        detail = (run.stderr or run.stdout or "").strip()[-300:]
        return f"hermes cannot reach a model provider: {detail or 'no output'}"
    return None
