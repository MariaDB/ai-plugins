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
rem mariadb-mcp-launcher.cmd -- Windows launcher for the mariadb-shell MCP server.
rem
rem Resolution order:
rem   1. %MARIADB_SHELL_BIN%, if set (explicit override).
rem   2. A mariadb-shell on %PATH% whose version is >= MARIADB_SHELL_VERSION.
rem   3. A local install at %MARIADB_SHELL_BINDIR%\mariadb-shell.cmd (default
rem      %LOCALAPPDATA%\Programs\mariadb-shell\bin) at that version or newer.
rem   4. Otherwise fetch the official installer, install.ps1, from a pinned
rem      mariadb-shell commit and install release v%MARIADB_SHELL_VERSION% -- the
rem      one this plugin release was tested with, prerelease or not -- under
rem      %LOCALAPPDATA%\Programs\mariadb-shell, with .cmd shims in its bin dir;
rem      then launch what it installed.
rem
rem Installing is delegated to install.ps1 rather than reimplemented here: it
rem picks the package matching the local CPU and verifies its checksum. The
rem checksums come from mariadb-shell-<tag>.SHA256SUMS next to this script, a
rem copy of that release's SHA256SUMS committed with the plugin, so a package
rem replaced on the release after the fact is refused. Nothing in this launcher
rem needs to know how release assets are named.
rem
rem This copy is Hermes' own: the other harnesses' launchers install the newest
rem release from the installer on main.
rem
rem However it resolves, the binary is run as
rem   mariadb-shell -- mcp start-server --transport=stdio
rem so the MCP server runs over stdio (not HTTP). stdout therefore belongs to the
rem MCP transport alone: every message from this script, and from the installer
rem it runs, is redirected to stderr instead.
rem
rem Environment:
rem   MARIADB_SHELL_VERSION     Minimum acceptable version (default below).
rem   MARIADB_SHELL_BIN         Pre-installed binary; skips all other logic.
rem   MARIADB_SHELL_BINDIR      Where install.ps1 writes its shims, and where
rem                             step 3 looks.
rem   MARIADB_SHELL_PREFIX      Passed through: where install.ps1 unpacks releases.
rem   MARIADB_SHELL_TAG         Release tag to install (default
rem                             v%MARIADB_SHELL_VERSION%). A tag with no committed
rem                             SHA256SUMS next to this script is checked against
rem                             the release's own.
rem   MARIADB_SHELL_REPO        Passed through: owner/repo to install from.
rem ============================================================================

if not defined MARIADB_SHELL_VERSION set "MARIADB_SHELL_VERSION=26.10.4"
if not defined MARIADB_SHELL_REPO set "MARIADB_SHELL_REPO=mariadb-corporation/mariadb-shell"
if not defined MARIADB_SHELL_BINDIR set "MARIADB_SHELL_BINDIR=%LOCALAPPDATA%\Programs\mariadb-shell\bin"

if not defined MARIADB_SHELL_TAG set "MARIADB_SHELL_TAG=v%MARIADB_SHELL_VERSION%"

rem The mariadb-shell commit the installer is taken from: fixed, so the script
rem that runs is the one this launcher was tested with, not whatever main holds.
rem Move it only when the installers change in a way the launcher needs.
set "INSTALLER_COMMIT=664993ccbc523cc82218251fcbe9c2fb8a209cdb"
set "INSTALLER_URL=https://raw.githubusercontent.com/%MARIADB_SHELL_REPO%/%INSTALLER_COMMIT%/install.ps1"
set "SUMS_FILE=%~dp0mariadb-shell-%MARIADB_SHELL_TAG%.SHA256SUMS"
set "LOCAL_BIN=%MARIADB_SHELL_BINDIR%\mariadb-shell.cmd"

rem Arguments that start the mariadb-shell MCP server over stdio.
set "MCP_ARGS=-- mcp start-server --transport=stdio"

rem --- 1. Escape hatch: explicit binary ---------------------------------------
if not defined MARIADB_SHELL_BIN goto try_path
call "%MARIADB_SHELL_BIN%" %MCP_ARGS%
exit /b %errorlevel%

rem --- 2. A mariadb-shell already on PATH -------------------------------------
:try_path
set "PATH_BIN="
for /f "delims=" %%P in ('where mariadb-shell 2^>nul') do if not defined PATH_BIN set "PATH_BIN=%%P"
if not defined PATH_BIN goto try_local

call :check_version "%PATH_BIN%"
if errorlevel 1 goto path_too_old
echo mariadb-mcp-launcher: using mariadb-shell from PATH: %PATH_BIN% [%CAND_VER%] 1>&2
call "%PATH_BIN%" %MCP_ARGS%
exit /b %errorlevel%

:path_too_old
echo mariadb-mcp-launcher: mariadb-shell on PATH does not meet required %MARIADB_SHELL_VERSION%; looking for a managed install 1>&2

rem --- 3. An existing local install --------------------------------------------
:try_local
if not exist "%LOCAL_BIN%" goto install
call :check_version "%LOCAL_BIN%"
if errorlevel 1 goto local_too_old
echo mariadb-mcp-launcher: using installed mariadb-shell: %LOCAL_BIN% [%CAND_VER%] 1>&2
call "%LOCAL_BIN%" %MCP_ARGS%
exit /b %errorlevel%

:local_too_old
echo mariadb-mcp-launcher: installed mariadb-shell at %LOCAL_BIN% does not meet required %MARIADB_SHELL_VERSION%; installing %MARIADB_SHELL_TAG% 1>&2

rem --- 4. Install the pinned release ------------------------------------------
rem mariadb-shell is public: nothing here sends credentials, and nothing reads
rem another tool's stored login.
rem
rem A tag the plugin carries no SHA256SUMS for was chosen by whoever set
rem MARIADB_SHELL_TAG or MARIADB_SHELL_VERSION; that release's own is used then.
:install
set "MARIADB_SHELL_SHA256SUMS="
if exist "%SUMS_FILE%" set "MARIADB_SHELL_SHA256SUMS=%SUMS_FILE%"
if not defined MARIADB_SHELL_SHA256SUMS echo mariadb-mcp-launcher: no committed checksums for %MARIADB_SHELL_TAG%; checking against the release's own SHA256SUMS 1>&2

set "INSTALL_FAILED=0"
set "PS_INSTALLER=%TEMP%\mariadb-shell-install-%RANDOM%.ps1"

echo mariadb-mcp-launcher: no suitable mariadb-shell found; installing %MARIADB_SHELL_TAG% from %MARIADB_SHELL_REPO% ... 1>&2
echo mariadb-mcp-launcher: a first install can take a minute. If the harness gives up on this server meanwhile (Claude Code waits 30 s unless MCP_TIMEOUT is raised), the install still finishes: reconnect the server then (/mcp in Claude Code), or start a new session. 1>&2
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "try{ [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 }catch{};" ^
  "Invoke-WebRequest -UseBasicParsing -Uri $env:INSTALLER_URL -OutFile $env:PS_INSTALLER" 1>&2
if errorlevel 1 goto download_failed

rem MARIADB_SHELL_BINDIR, MARIADB_SHELL_TAG and MARIADB_SHELL_SHA256SUMS are
rem already in this process's environment, which is where install.ps1 reads them,
rem so the shims land exactly where step 3 looks. A pinned tag needs no
rem prerelease handling: the installer takes a named release whether or not it
rem is a prerelease.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_INSTALLER%" 1>&2
if errorlevel 1 goto installer_failed
del /q "%PS_INSTALLER%" >nul 2>&1
goto after_install

:installer_failed
set "INSTALL_FAILED=1"
echo mariadb-mcp-launcher: the mariadb-shell installer failed 1>&2
del /q "%PS_INSTALLER%" >nul 2>&1
goto after_install

:download_failed
set "INSTALL_FAILED=1"
echo mariadb-mcp-launcher: error: could not download the installer from %INSTALLER_URL% 1>&2

rem A concurrent launcher may have completed the install that this one lost the
rem race for, so the binary -- not the installer's exit status -- is the last word.
:after_install
if not exist "%LOCAL_BIN%" goto no_binary
if "%INSTALL_FAILED%"=="1" echo mariadb-mcp-launcher: using the mariadb-shell already present at %LOCAL_BIN% 1>&2

rem Below the required version is worth saying, but not worth refusing to start
rem over: a MARIADB_SHELL_TAG older than the floor was asked for by name.
call :check_version "%LOCAL_BIN%"
if errorlevel 1 echo mariadb-mcp-launcher: warning: installed mariadb-shell [%CAND_VER%] is below the required %MARIADB_SHELL_VERSION%; starting it anyway 1>&2

echo mariadb-mcp-launcher: starting mariadb-shell MCP server: %LOCAL_BIN% 1>&2
call "%LOCAL_BIN%" %MCP_ARGS%
exit /b %errorlevel%

:no_binary
echo mariadb-mcp-launcher: error: no mariadb-shell at %LOCAL_BIN% after installing 1>&2
echo mariadb-mcp-launcher: install it by hand, then retry: 1>&2
echo     $env:MARIADB_SHELL_TAG = '%MARIADB_SHELL_TAG%' 1>&2
echo     irm https://github.com/%MARIADB_SHELL_REPO%/raw/%INSTALLER_COMMIT%/install.ps1 ^| iex 1>&2
exit /b 1

rem ============================================================================
rem check_version %1 -- is that binary usable and at least MARIADB_SHELL_VERSION?
rem Sets CAND_VER to the version line it reported. Exits 0 when acceptable, 1
rem when too old, 2 when no version could be read.
rem
rem The version line looks like "mariadb-shell   Ver 26.8.0 for windows ...", so
rem the number after "Ver" is read first; a bare numeric match is only the
rem fallback, since the leading path may itself carry digits.
rem ============================================================================
:check_version
set "CAND=%~1"
set "CAND_VER="
if not exist "%CAND%" exit /b 2
for /f "usebackq delims=" %%V in (`"%CAND%" --version 2^>nul`) do if not defined CAND_VER set "CAND_VER=%%V"
if not defined CAND_VER exit /b 2
powershell -NoProfile -Command ^
  "$t=$env:CAND_VER;" ^
  "$m=[regex]::Match($t,'(?i)ver\s+(\d+(\.\d+)+)');" ^
  "$v = if($m.Success){ $m.Groups[1].Value } else { $b=[regex]::Match($t,'\d+(\.\d+)+'); if($b.Success){ $b.Value } else { '' } };" ^
  "if(-not $v){ exit 2 };" ^
  "try{ if([version]$v -ge [version]$env:MARIADB_SHELL_VERSION){ exit 0 } else { exit 1 } }catch{ exit 2 }"
exit /b %errorlevel%
