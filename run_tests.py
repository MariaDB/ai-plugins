#!/usr/bin/env python3
#
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
#
# run_tests.py — run every plugin test suite in this repo with the Python that
# ships inside mariadb-shell, and collect one combined coverage report.
#
# This mirrors the runner used by the mariadb-shell MCP plugin
# (mysql-shell-plugins/mcp_plugin/run_tests.py): tests execute under
# `mariadb-shell --pym pytest` rather than a system/venv Python, so the suites
# run against the same interpreter and package set as the MCP server they
# exercise, and coverage is recorded the same way (term + XML + HTML reports
# plus a JUnit XML per suite).
#
# The suites live one per agent (claude/, codex/, opencode/, pi/, hermes/) and each has
# its own conftest.py, so they are discovered from disk and run as separate
# pytest processes — their same-named test modules and `lib` packages would
# collide in a single process. Coverage data is appended across the runs, so the
# reports written by the last suite cover all of them.
#
# Usage:
#
#   ./run_tests.py                      # every suite, default tiers (static + db)
#   ./run_tests.py claude               # one suite (name = its top-level dir)
#   ./run_tests.py -m static            # a single tier, all suites
#   ./run_tests.py claude -m e2e        # the opt-in end-to-end tier
#   ./run_tests.py -k create_table      # only tests matching a pattern
#   ./run_tests.py -- --lf -x           # anything after `--` goes to pytest
#
#   npm test                            # same thing, via package.json
#   mariadb-shell --py -f run_tests.py   # or driven by the shell itself
#
# The mariadb-shell binary is taken from --shell, else $MARIADB_SHELL, else
# PATH. Its directory is prepended to the PATH the suites see, so the e2e tier's
# MCP launcher resolves the same binary.
#
# Unlike the mcp_plugin runner this does NOT relocate the shell's user config
# home by default: the e2e tests that need an isolated one create it themselves,
# and the sandbox tier expects the real one. Pass --userhome to override.

# cSpell:ignore mysqlsh userhome junitxml pym

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PYTEST_INI = REPO_ROOT / "pytest-coverage.ini"
COVERAGE_RC = REPO_ROOT / ".coveragerc"
REPORT_DIR = REPO_ROOT / "test-results"

# pytest's "no tests were collected" exit code — expected when a marker
# expression matches nothing in a suite (e.g. -m e2e outside claude/).
EXIT_NO_TESTS_COLLECTED = 5


def _discover_suites() -> dict[str, Path]:
    """Map suite name -> directory for every plugin test suite in the repo.

    A suite is any `<agent>/dev-plugin-test*/` directory holding a conftest.py;
    the suite is named after its top-level (agent) directory. Discovering rather
    than hardcoding means a new agent's suite is picked up automatically, and
    the two spellings in use (`dev-plugin-tests` and `dev-plugin-test`) both
    match.
    """
    suites: dict[str, Path] = {}
    for conftest in sorted(REPO_ROOT.glob("*/dev-plugin-test*/conftest.py")):
        suite_dir = conftest.parent
        suites[suite_dir.parent.name] = suite_dir
    return suites


def _resolve_shell(explicit: str | None) -> str:
    shell = (
        explicit
        or os.environ.get("MARIADB_SHELL")
        or shutil.which("mariadb-shell.exe" if os.name == "nt" else "mariadb-shell")
    )
    assert shell is not None, (
        "Could not find the mariadb-shell binary. Set MARIADB_SHELL or pass --shell."
    )
    return str(Path(shell).resolve())


def _build_env(shell: str, userhome: str | None) -> dict[str, str]:
    env = os.environ.copy()
    env["MARIADB_SHELL"] = shell
    # What the e2e tier reads to locate the shell; keep any existing value.
    env.setdefault("MARIADB_SHELL_BIN", shell)
    env["MARIADB_SHELL_TERM_COLOR_MODE"] = "nocolor"
    # So `mariadb-shell` on PATH is the binary we were asked to test with —
    # the e2e MCP launcher resolves it that way.
    shell_bin_dir = str(Path(shell).parent)
    path = env.get("PATH", "")
    if shell_bin_dir not in path.split(os.pathsep):
        env["PATH"] = f"{shell_bin_dir}{os.pathsep}{path}" if path else shell_bin_dir
    if userhome:
        # Both spellings: the fork honours MYSQLSH_USER_CONFIG_HOME, newer
        # builds also read the MARIADB_SHELL_ name.
        Path(userhome).mkdir(parents=True, exist_ok=True)
        env["MYSQLSH_USER_CONFIG_HOME"] = userhome
        env["MARIADB_SHELL_USER_CONFIG_HOME"] = userhome
    return env


def _erase_coverage() -> None:
    """Drop data from earlier runs so the combined report is for this run only."""
    for stale in [REPO_ROOT / ".coverage", *REPO_ROOT.glob(".coverage.*")]:
        stale.unlink(missing_ok=True)


def _run(command: list[str], env: dict[str, str]) -> int:
    print(f"\n$ {' '.join(command)}", flush=True)
    return subprocess.run(command, env=env, cwd=REPO_ROOT).returncode


def _install_requirements(shell: str, suites: dict[str, Path], env: dict[str, str]) -> int:
    """Install each suite's declared test dependencies into the shell's Python."""
    requirements: list[str] = []
    for suite_dir in suites.values():
        req = suite_dir / "requirements.txt"
        if req.is_file():
            requirements += ["-r", str(req)]
    if not requirements:
        return 0
    return _run([shell, "--pym", "pip", "install", *requirements], env)


def _pytest_command(
    shell: str,
    suite: str,
    suite_dir: Path,
    cov_targets: list[Path],
    args: argparse.Namespace,
    extra: list[str],
) -> list[str]:
    command = [shell, "--pym", "pytest", "-c", str(PYTEST_INI)]
    if args.no_coverage:
        command.append("--no-cov")
    else:
        # Every selected suite is a coverage source on every run, so the
        # reports the last suite writes describe the whole run rather than
        # just its own tree. --cov-append accumulates the data across runs.
        for target in cov_targets:
            command.append(f"--cov={target}")
        command += ["--cov-append", f"--cov-config={COVERAGE_RC}"]
    command.append(f"--junitxml={REPORT_DIR / f'{suite}-tests.xml'}")
    if args.markers:
        command += ["-m", args.markers]
    if args.only:
        command += ["-k", args.only]
    command += ["-vv", "-W", "ignore::DeprecationWarning", str(suite_dir)]
    return command + extra


def main() -> int:
    available = _discover_suites()

    parser = argparse.ArgumentParser(
        description="Run the plugin test suites with the mariadb-shell Python.",
        epilog="Anything after a bare `--` is forwarded to pytest unchanged.",
    )
    parser.add_argument(
        "suites",
        nargs="*",
        metavar="SUITE",
        help=f"suites to run (default: all — {', '.join(available) or 'none found'})",
    )
    parser.add_argument(
        "-s",
        "--shell",
        default=os.environ.get("MARIADB_SHELL"),
        help="path to the mariadb-shell binary (default: $MARIADB_SHELL, else PATH)",
    )
    parser.add_argument(
        "-u",
        "--userhome",
        default=None,
        help="shell user config home for the run (default: the real one, untouched)",
    )
    parser.add_argument(
        "-m",
        "--markers",
        default=None,
        help="pytest marker expression, e.g. 'static' or 'e2e' "
        "(default: the tiers enabled in pytest-coverage.ini)",
    )
    parser.add_argument(
        "-k", "--only", default=None, help="only run tests matching this pattern"
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="skip installing the suites' requirements into the shell's Python",
    )
    parser.add_argument(
        "--no-coverage", action="store_true", help="run without coverage measurement"
    )
    # Split on the first bare `--` ourselves: argparse would swallow it and then
    # read the pytest flags after it as positional suite names.
    argv = sys.argv[1:]
    if "--" in argv:
        separator = argv.index("--")
        argv, extra = argv[:separator], argv[separator + 1 :]
    else:
        extra = []
    args = parser.parse_args(argv)

    if not available:
        print("No test suites found (looked for */dev-plugin-test*/conftest.py).")
        return 1

    unknown = [s for s in args.suites if s not in available]
    if unknown:
        print(
            f"Unknown suite(s): {', '.join(unknown)}. "
            f"Available: {', '.join(available)}."
        )
        return 2

    selected = {name: available[name] for name in (args.suites or available)}
    shell = _resolve_shell(args.shell)
    env = _build_env(shell, args.userhome)
    REPORT_DIR.mkdir(exist_ok=True)

    print(f"mariadb-shell: {shell}")
    print(f"suites:        {', '.join(selected)}")

    if not args.no_install:
        rc = _install_requirements(shell, selected, env)
        if rc != 0:
            print("Failed to install the test dependencies.")
            return rc

    if not args.no_coverage:
        _erase_coverage()

    cov_targets = list(selected.values())
    results: dict[str, int] = {}
    for suite, suite_dir in selected.items():
        command = _pytest_command(shell, suite, suite_dir, cov_targets, args, extra)
        results[suite] = _run(command, env)

    print("\n" + "=" * 72)
    for suite, rc in results.items():
        if rc == 0:
            status = "PASSED"
        elif rc == EXIT_NO_TESTS_COLLECTED:
            status = "no tests selected"
        else:
            status = f"FAILED (exit {rc})"
        print(f"{suite:<12} {status}")
    if not args.no_coverage:
        print(
            f"\ncoverage: {REPORT_DIR.name}/coverage.xml, htmlcov/index.html; "
            f"JUnit XML: {REPORT_DIR.name}/<suite>-tests.xml"
        )
    print("=" * 72)

    failures = [rc for rc in results.values() if rc not in (0, EXIT_NO_TESTS_COLLECTED)]
    return failures[0] if failures else 0


if __name__ == "__main__":
    sys.exit(main())
