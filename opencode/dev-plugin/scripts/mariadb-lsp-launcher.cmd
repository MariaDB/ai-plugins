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
rem mariadb-lsp-launcher.cmd -- Windows launcher for mariadb-lsp, the MariaDB
rem SQL language server that ships in the mariadb-shell package.
rem
rem This launcher NEVER installs anything: installing mariadb-shell is the job
rem of mariadb-mcp-launcher.cmd alone, so a harness starting both servers at
rem once downloads the package once. When no suitable mariadb-shell is present
rem yet, it waits for the MCP launcher's install (MARIADB_LSP_WAIT seconds).
rem
rem Resolution order (see mariadb-lsp-launcher.sh for the reasoning):
rem   1. %MARIADB_LSP_BIN%, if set (explicit override).
rem   2. The mariadb-shell the MCP launcher would run -- %MARIADB_SHELL_BIN%, a
rem      mariadb-shell on %PATH% at >= MARIADB_SHELL_VERSION, or
rem      %MARIADB_SHELL_BINDIR%\mariadb-shell.cmd at that version -- and the
rem      mariadb-lsp(.cmd/.exe) beside it. install.ps1 writes both shims into
rem      the same bin dir.
rem   3. No such shell yet: wait for the MCP launcher to install one, then 2.
rem   4. A shell without mariadb-lsp: any mariadb-lsp on %PATH% or in
rem      %MARIADB_SHELL_BINDIR%.
rem
rem It is run as
rem   mariadb-lsp lsp [args passed to this script...]
rem which speaks LSP over stdin and stdout, so every message from this script
rem goes to stderr.
rem
rem Environment:
rem   MARIADB_SHELL_VERSION  Minimum mariadb-shell version (default below).
rem   MARIADB_SHELL_BIN      As for the MCP launcher: the shell to pair with.
rem   MARIADB_SHELL_BINDIR   Where install.ps1 writes its shims.
rem   MARIADB_LSP_BIN        Path to a mariadb-lsp; skips all other logic.
rem   MARIADB_LSP_WAIT       Seconds to wait for the MCP launcher's install
rem                          (default 180; 0 does not wait).
rem ============================================================================

rem A harness or terminal running PowerShell 7 passes on its PSModulePath, and
rem Windows PowerShell 5.1, which this script runs, then loads PowerShell 7's
rem modules and loses cmdlets such as Get-FileHash. Without the variable, 5.1
rem builds its own default. setlocal keeps this to the launcher and its children.
set "PSModulePath="

if not defined MARIADB_SHELL_VERSION set "MARIADB_SHELL_VERSION=26.11.2"
if not defined MARIADB_SHELL_BINDIR set "MARIADB_SHELL_BINDIR=%LOCALAPPDATA%\Programs\mariadb-shell\bin"
if not defined MARIADB_LSP_WAIT set "MARIADB_LSP_WAIT=180"

set "LOCAL_BIN=%MARIADB_SHELL_BINDIR%\mariadb-shell.cmd"
set "SHELL_BIN="
set "LSP_BIN="
set /a WAITED=0

rem --- 1. Escape hatch: explicit binary ---------------------------------------
if not defined MARIADB_LSP_BIN goto find_shell
if not exist "%MARIADB_LSP_BIN%" goto no_lsp_bin
call "%MARIADB_LSP_BIN%" lsp %*
exit /b %errorlevel%

:no_lsp_bin
echo mariadb-lsp-launcher: error: MARIADB_LSP_BIN does not exist: %MARIADB_LSP_BIN% 1>&2
exit /b 1

rem --- 2. The shell the MCP launcher runs --------------------------------------
:find_shell
if not defined MARIADB_SHELL_BIN goto try_path
if exist "%MARIADB_SHELL_BIN%" set "SHELL_BIN=%MARIADB_SHELL_BIN%"
goto have_shell

:try_path
set "PATH_BIN="
for /f "delims=" %%P in ('where mariadb-shell 2^>nul') do if not defined PATH_BIN set "PATH_BIN=%%P"
if not defined PATH_BIN goto try_local
call :check_version "%PATH_BIN%"
if errorlevel 1 goto try_local
set "SHELL_BIN=%PATH_BIN%"
goto have_shell

:try_local
if not exist "%LOCAL_BIN%" goto no_shell
rem With the bin dir on PATH (the usual setup), PATH already offered this file.
if /i "%PATH_BIN%"=="%LOCAL_BIN%" goto no_shell
call :check_version "%LOCAL_BIN%"
if errorlevel 1 goto no_shell
set "SHELL_BIN=%LOCAL_BIN%"
goto have_shell

rem --- 3. Wait for the MCP launcher's install ---------------------------------
rem `timeout` refuses to run with redirected stdin, which a language server
rem always has; ping sleeps without stdin, and without the PowerShell start-up
rem that would add up to a second to every 2 s tick.
:no_shell
if %WAITED% GEQ %MARIADB_LSP_WAIT% goto any_lsp
if %WAITED%==0 echo mariadb-lsp-launcher: no mariadb-shell ^>= %MARIADB_SHELL_VERSION% yet; waiting up to %MARIADB_LSP_WAIT%s for the MCP server's launcher to install it 1>&2
ping -n 3 127.0.0.1 >nul 2>&1
set /a WAITED+=2
goto find_shell

:have_shell
if not defined SHELL_BIN goto any_lsp
for %%D in ("%SHELL_BIN%") do set "SHELL_DIR=%%~dpD"
for %%N in (mariadb-lsp.cmd mariadb-lsp.exe) do if not defined LSP_BIN if exist "%SHELL_DIR%%%N" set "LSP_BIN=%SHELL_DIR%%%N"
if defined LSP_BIN goto start
rem A shell that turned up while we waited comes from an install still under
rem way: install.ps1 writes mariadb-lsp.cmd a moment after mariadb-shell.cmd.
rem Give it one more tick before deciding there is none.
if %WAITED%==0 goto no_lsp_beside
if defined LSP_RECHECKED goto no_lsp_beside
set "LSP_RECHECKED=1"
ping -n 3 127.0.0.1 >nul 2>&1
goto have_shell

:no_lsp_beside
echo mariadb-lsp-launcher: the mariadb-shell at %SHELL_BIN% has no mariadb-lsp beside it 1>&2

rem --- 4. Any mariadb-lsp at all ------------------------------------------------
:any_lsp
for /f "delims=" %%L in ('where mariadb-lsp 2^>nul') do if not defined LSP_BIN set "LSP_BIN=%%L"
if not defined LSP_BIN if exist "%MARIADB_SHELL_BINDIR%\mariadb-lsp.cmd" set "LSP_BIN=%MARIADB_SHELL_BINDIR%\mariadb-lsp.cmd"
if not defined LSP_BIN goto no_lsp
if not defined SHELL_BIN echo mariadb-lsp-launcher: warning: no mariadb-shell ^>= %MARIADB_SHELL_VERSION% found; using the mariadb-lsp present 1>&2

:start
echo mariadb-lsp-launcher: starting %LSP_BIN% 1>&2
call "%LSP_BIN%" lsp %*
exit /b %errorlevel%

:no_lsp
echo mariadb-lsp-launcher: error: no mariadb-lsp found. 1>&2
echo   It ships in the mariadb-shell packages from %MARIADB_SHELL_VERSION% on, which the MariaDB MCP 1>&2
echo   server's launcher installs into %MARIADB_SHELL_BINDIR% on its first start. Start a 1>&2
echo   session with the plugin's MCP server enabled, or install by hand: 1>&2
echo       irm https://github.com/mariadb-corporation/mariadb-shell/raw/main/install.ps1 ^| iex 1>&2
echo   To use a binary of your own, set MARIADB_LSP_BIN. 1>&2
exit /b 1

rem ============================================================================
rem check_version %1 -- is that binary usable and at least MARIADB_SHELL_VERSION?
rem Sets CAND_VER to the version it reported. Exits 0 when acceptable, 1 when
rem too old, 2 when no version could be read.
rem
rem All of the --version output is read, not only its first line: a build can
rem print plugin registration errors before "mariadb-shell   Ver 26.8.0 for
rem windows ...". Reading it to the end also lets the shell restore the console
rem code page it switches to. [version] compares field by field, so 26.10 is
rem above 26.9.
rem ============================================================================
:check_version
set "CAND=%~1"
set "CAND_VER="
set "CAND_STATE="
if not exist "%CAND%" exit /b 2
for /f "usebackq tokens=1,2" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$o = @(& $env:CAND --version 2>$null) -join ' '; $m = [regex]::Match($o, '(?i)\bver\s+(\d+(\.\d+)+)'); if (-not $m.Success) { 'none'; exit }; $v = $m.Groups[1].Value; try { if ([version]$v -ge [version]$env:MARIADB_SHELL_VERSION) { 'ok ' + $v } else { 'old ' + $v } } catch { 'none ' + $v }"`) do (
  set "CAND_STATE=%%A"
  set "CAND_VER=%%B"
)
if "%CAND_STATE%"=="ok" exit /b 0
if "%CAND_STATE%"=="old" exit /b 1
exit /b 2
