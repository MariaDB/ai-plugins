@echo off
setlocal
rem Copyright (c) 2026, MariaDB plc.
rem
rem This program is free software; you can redistribute it and/or modify
rem it under the terms of the GNU General Public License, version 2.0,
rem as published by the Free Software Foundation.
rem
rem This program is distributed in the hope that it will be useful, but
rem WITHOUT ANY WARRANTY; without even the implied warranty of
rem MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
rem the GNU General Public License, version 2.0, for more details.
rem
rem You should have received a copy of the GNU General Public License
rem along with this program; if not, write to the Free Software Foundation, Inc.,
rem 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

rem ============================================================================
rem setup-codex-mcp.cmd -- register the mariadb-shell MCP server with Codex,
rem                        on native Windows. The counterpart of
rem                        setup-codex-mcp.sh.
rem
rem This is a FALLBACK, not a required step. The plugin's own .mcp.json declares a
rem working server: a relative command plus "cwd": "." (which Codex resolves to
rem the plugin's install directory), naming the extensionless
rem scripts/mariadb-mcp-launcher, which Codex resolves through %PATHEXT% here and
rem so lands on mariadb-mcp-launcher.cmd. See that file for why. Use this script
rem when that does not take effect -- an older Codex, or a host where the
rem extensionless resolution does not hold.
rem
rem `codex mcp add` writes an ordinary [mcp_servers.mariadb] entry into
rem %CODEX_HOME%\config.toml with the absolute path resolved here, and it takes
rem precedence over the plugin-provided entry of the same name.
rem
rem This registers the **.cmd** launcher, which is the point of having a separate
rem script: Codex spawns the command directly, so a .sh path -- what the bash
rem version writes, even when run from Git Bash -- is not executable on native
rem Windows.
rem
rem Usage:
rem   codex\dev-plugin\scripts\setup-codex-mcp.cmd            register (or update)
rem   codex\dev-plugin\scripts\setup-codex-mcp.cmd --remove   unregister
rem
rem Environment:
rem   CODEX_HOME              Codex config dir to write to (default %USERPROFILE%\.codex).
rem   CODEX_BIN               codex binary to use (default: the one on PATH).
rem   MARIADB_SHELL_VERSION   Minimum mariadb-shell version to pass to the launcher.
rem ============================================================================

set "SERVER_NAME=mariadb"
if not defined MARIADB_SHELL_VERSION set "MARIADB_SHELL_VERSION=26.9.3"

rem %~dp0 is this script's directory, with a trailing backslash.
set "PLUGIN_ROOT=%~dp0.."
set "LAUNCHER=%~dp0mariadb-mcp-launcher.cmd"

set "CODEX=%CODEX_BIN%"
if not defined CODEX for %%C in (codex.exe codex.cmd codex) do if not defined CODEX set "CODEX=%%~$PATH:C"
if not defined CODEX (
  echo error: codex not found ^(set CODEX_BIN or add it to PATH^) 1>&2
  exit /b 1
)
if not exist "%LAUNCHER%" (
  echo error: launcher not found: %LAUNCHER% 1>&2
  exit /b 1
)

if /i "%~1"=="--remove" (
  "%CODEX%" mcp remove "%SERVER_NAME%"
  exit /b %errorlevel%
)

rem Re-registering the same name is how an update is done, so drop any existing
rem entry first rather than letting `add` fail on the collision.
"%CODEX%" mcp remove "%SERVER_NAME%" >nul 2>&1

"%CODEX%" mcp add "%SERVER_NAME%" --env "MARIADB_SHELL_VERSION=%MARIADB_SHELL_VERSION%" -- "%LAUNCHER%"
if errorlevel 1 (
  echo error: codex mcp add failed 1>&2
  exit /b 1
)

echo Registered MCP server '%SERVER_NAME%' -^> %LAUNCHER%
echo Verify with: "%CODEX%" mcp get %SERVER_NAME%
