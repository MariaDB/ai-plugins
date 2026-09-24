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
rem   4. Otherwise fetch and run the official installer,
rem      https://raw.githubusercontent.com/mariadb-corporation/mariadb-shell/main/install.ps1,
rem      which unpacks the newest release under %LOCALAPPDATA%\Programs\mariadb-shell
rem      and writes .cmd shims into its bin dir -- then launch what it installed.
rem
rem Installing is delegated to install.ps1 rather than reimplemented here: it
rem picks the package matching the local CPU, reads the asset list from the
rem release's own SHA256SUMS and verifies the checksum. Nothing in this launcher
rem needs to know how release assets are named.
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
rem   MARIADB_SHELL_TAG         Passed through: install this release tag.
rem   MARIADB_SHELL_PRERELEASE  Normally unset: a stable release is preferred, and
rem                             a prerelease installed only when there is no stable
rem                             one. Set to 1 to go straight for a prerelease, or
rem                             to 0 to refuse one entirely.
rem   MARIADB_SHELL_REPO        Passed through: owner/repo to install from.
rem   MARIADB_SHELL_TOKEN       Token for a private repository. GH_TOKEN and
rem                             GITHUB_TOKEN are consulted too, then
rem                             `gh auth token` -- install.ps1's own order.
rem ============================================================================

if not defined MARIADB_SHELL_VERSION set "MARIADB_SHELL_VERSION=26.9.4"
if not defined MARIADB_SHELL_REPO set "MARIADB_SHELL_REPO=mariadb-corporation/mariadb-shell"
if not defined MARIADB_SHELL_BINDIR set "MARIADB_SHELL_BINDIR=%LOCALAPPDATA%\Programs\mariadb-shell\bin"

set "INSTALLER_URL=https://raw.githubusercontent.com/%MARIADB_SHELL_REPO%/main/install.ps1"
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
echo mariadb-mcp-launcher: installed mariadb-shell at %LOCAL_BIN% does not meet required %MARIADB_SHELL_VERSION%; installing the newest release 1>&2

rem --- 4. Install the newest release -------------------------------------------
rem The token is resolved here as well as inside install.ps1 because fetching the
rem installer from a private repository needs it too -- raw.githubusercontent.com
rem answers 404, not 401, without credentials. It is exported under the name
rem install.ps1 reads, so one lookup serves both.
:install
if not defined MARIADB_SHELL_TOKEN set "MARIADB_SHELL_TOKEN=%GH_TOKEN%"
if not defined MARIADB_SHELL_TOKEN set "MARIADB_SHELL_TOKEN=%GITHUB_TOKEN%"
if defined MARIADB_SHELL_TOKEN goto have_token
for /f "delims=" %%T in ('gh auth token 2^>nul') do if not defined MARIADB_SHELL_TOKEN set "MARIADB_SHELL_TOKEN=%%T"
:have_token

set "INSTALL_FAILED=0"
set "PS_INSTALLER=%TEMP%\mariadb-shell-install-%RANDOM%.ps1"

echo mariadb-mcp-launcher: no suitable mariadb-shell found; installing from %MARIADB_SHELL_REPO% ... 1>&2
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue';" ^
  "try{ [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 }catch{};" ^
  "$h=@{}; if($env:MARIADB_SHELL_TOKEN){ $h['Authorization']='Bearer ' + $env:MARIADB_SHELL_TOKEN };" ^
  "Invoke-WebRequest -Headers $h -Uri $env:INSTALLER_URL -OutFile $env:PS_INSTALLER" 1>&2
if errorlevel 1 goto download_failed

rem MARIADB_SHELL_BINDIR is already in this process's environment, so the shims
rem land exactly where step 3 looks; MARIADB_SHELL_TAG is read by the installer
rem from there too.
rem
rem Prereleases: wanted when they are all there is, but not preferred over a
rem stable release. install.ps1 skips them exactly as /releases/latest does, so a
rem repository whose only release is a prerelease has nothing to install and this
rem first attempt fails -- the retry below then gets it, with no decision needed
rem from whoever is running this. MARIADB_SHELL_PRERELEASE short-circuits the
rem choice: truthy goes straight for the prerelease, an explicit 0/false/no keeps
rem the install stable-only.
if not defined MARIADB_SHELL_PRERELEASE goto install_stable_first
if /i "%MARIADB_SHELL_PRERELEASE%"=="0" goto install_stable_only
if /i "%MARIADB_SHELL_PRERELEASE%"=="false" goto install_stable_only
if /i "%MARIADB_SHELL_PRERELEASE%"=="no" goto install_stable_only
if /i "%MARIADB_SHELL_PRERELEASE%"=="off" goto install_stable_only
rem Truthy: the installer reads MARIADB_SHELL_PRERELEASE itself, so one run does it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_INSTALLER%" 1>&2
if errorlevel 1 goto installer_failed
goto installer_done

:install_stable_only
set "MARIADB_SHELL_PRERELEASE="
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_INSTALLER%" 1>&2
if errorlevel 1 goto installer_failed
goto installer_done

:install_stable_first
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_INSTALLER%" 1>&2
if not errorlevel 1 goto installer_done
echo mariadb-mcp-launcher: no stable release to install; retrying with a prerelease 1>&2
set "MARIADB_SHELL_PRERELEASE=1"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_INSTALLER%" 1>&2
if errorlevel 1 goto installer_failed
echo mariadb-mcp-launcher: installed a prerelease -- no stable %MARIADB_SHELL_REPO% release is published yet 1>&2

:installer_done
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
if not defined MARIADB_SHELL_TOKEN echo mariadb-mcp-launcher: no token found -- while %MARIADB_SHELL_REPO% is private, set MARIADB_SHELL_TOKEN or GH_TOKEN, or run gh auth login 1>&2

rem A concurrent launcher may have completed the install that this one lost the
rem race for, so the binary -- not the installer's exit status -- is the last word.
:after_install
if not exist "%LOCAL_BIN%" goto no_binary
if "%INSTALL_FAILED%"=="1" echo mariadb-mcp-launcher: using the mariadb-shell already present at %LOCAL_BIN% 1>&2

rem Below the required version is worth saying, but not worth refusing to start
rem over: the newest published release is the best that can be had.
call :check_version "%LOCAL_BIN%"
if errorlevel 1 echo mariadb-mcp-launcher: warning: installed mariadb-shell [%CAND_VER%] is below the required %MARIADB_SHELL_VERSION%; starting it anyway 1>&2

echo mariadb-mcp-launcher: starting mariadb-shell MCP server: %LOCAL_BIN% 1>&2
call "%LOCAL_BIN%" %MCP_ARGS%
exit /b %errorlevel%

:no_binary
echo mariadb-mcp-launcher: error: no mariadb-shell at %LOCAL_BIN% after installing 1>&2
echo mariadb-mcp-launcher: install it by hand, then retry: 1>&2
echo     irm https://github.com/%MARIADB_SHELL_REPO%/raw/main/install.ps1 ^| iex 1>&2
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
