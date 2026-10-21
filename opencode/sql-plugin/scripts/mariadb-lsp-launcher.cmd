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

if not defined MARIADB_SHELL_VERSION set "MARIADB_SHELL_VERSION=26.10.3"
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
rem check_version %1 -- is that mariadb-shell at least MARIADB_SHELL_VERSION?
rem Exits 0 when acceptable, 1 when too old, 2 when no version could be read.
rem Same parsing as mariadb-mcp-launcher.cmd.
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
