---
layout: page
title: Offline Installation
subtitle: >-
  Install the plugin on a machine that cannot reach GitHub — two downloads, a
  few commands, and nothing fetched at run time.
badges: ["Claude Code", "macOS", "Linux", "Windows"]
permalink: /offline-install/
description: Install the MariaDB AI Plugins into Claude Code on a machine without access to GitHub — MariaDB Shell, the plugin and the sandbox server packages, all from downloaded files.
---

On first start the plugin normally downloads `mariadb-shell` from GitHub. On a
network that cannot reach GitHub, install the shell by hand instead, in the
place the plugin looks before it downloads anything, and install the plugin from
a local folder. Nothing is fetched at run time after that.

<div class="table-wrap" markdown="1">

| What | Version | Where it comes from |
| --- | --- | --- |
| AI Plugins — skills, MCP launcher, SQL language server launcher, CLI guard | the newest release | [ai-plugins releases]({{ site.repo }}/releases), source code archive |
| MariaDB Shell — runs the MCP server and the SQL language server | {{ site.shell_floor }} or newer | [mariadb-shell releases](https://github.com/mariadb-corporation/mariadb-shell/releases), one package per platform |
| MariaDB Server sandbox packages (optional) | 11.8.9, 12.3.3, 13.1.1 | [mariadb-shell v26.10.0](https://github.com/mariadb-corporation/mariadb-shell/releases/tag/v26.10.0) |

</div>

The plugin needs **MariaDB Shell {{ site.shell_floor }} or newer**. Given an
older one, it tries to download a newer one, which fails offline.

<div class="callout" markdown="1">
**Before you start:** Claude Code is installed on the target machine and can
reach its model provider — the Anthropic API, Amazon Bedrock, Google Vertex AI
or an internal gateway. This page covers only the MariaDB parts.
</div>

## Step 1 — Download on a connected machine
{: #step-1-download}

1. From the newest [ai-plugins release]({{ site.repo }}/releases), download
   **Source code (tar.gz)** for macOS and Linux, or **Source code (zip)** for
   Windows. The tar.gz keeps the launcher scripts executable.
2. From the [mariadb-shell v{{ site.shell_floor }} release](https://github.com/mariadb-corporation/mariadb-shell/releases/tag/v{{ site.shell_floor }}),
   or any newer one, download `SHA256SUMS` and the package for each platform
   your developers use:

   <div class="table-wrap" markdown="1">

   | Platform | Package |
   | --- | --- |
   | macOS 26+ on Apple silicon | `mariadb-shell-{{ site.shell_floor }}-macos26-arm-64bit.tar.gz` |
   | macOS 15+ on Intel | `mariadb-shell-{{ site.shell_floor }}-macos15-x86-64bit.tar.gz` |
   | Linux x86-64, glibc 2.34+ | `mariadb-shell-{{ site.shell_floor }}-linux-glibc2.34-x86-64bit.tar.gz` |
   | Linux ARM64, glibc 2.34+ | `mariadb-shell-{{ site.shell_floor }}-linux-glibc2.34-arm-64bit.tar.gz` |
   | Windows x86-64 | `mariadb-shell-{{ site.shell_floor }}-windows-x86-64bit.tar.gz` |
   | Windows ARM64 | `mariadb-shell-{{ site.shell_floor }}-windows-arm-64bit.tar.gz` |

   </div>

   `ldd --version` prints a Linux machine's glibc version. musl-based
   distributions such as Alpine are not supported.
3. Optionally, the [sandbox server packages](#sandbox-server-packages) for the
   MariaDB versions your developers want to test against.
4. Check the packages against their checksums, then copy everything into the
   restricted network:

   ```bash
   shasum -a 256 -c SHA256SUMS --ignore-missing     # macOS
   sha256sum -c SHA256SUMS --ignore-missing         # Linux
   ```

   ```powershell
   # Windows: compare this value with the package's line in SHA256SUMS
   (Get-FileHash .\mariadb-shell-{{ site.shell_floor }}-windows-x86-64bit.tar.gz -Algorithm SHA256).Hash
   ```

## Step 2 — Install MariaDB Shell by hand
{: #step-2-install-mariadb-shell}

Unpack the shell into the layout its online installer would create. The plugin
looks there before it tries to download anything, so with the shell in place it
never goes online. Do this on every developer machine, as the developer's own
user — not as root or Administrator.

### macOS and Linux

From the folder that holds the package, with `PKG` set to your platform's:

```bash
VER={{ site.shell_floor }}
PKG=mariadb-shell-$VER-linux-glibc2.34-x86-64bit
PREFIX="$HOME/.local/share/mariadb-shell"

mkdir -p "$PREFIX" "$HOME/.local/bin"
tar -xzf "$PKG.tar.gz" -C "$PREFIX"
mv "$PREFIX/$PKG" "$PREFIX/$VER"
ln -sfn "$PREFIX/$VER/bin/mariadb-shell" "$HOME/.local/bin/mariadb-shell"
ln -sfn "$PREFIX/$VER/bin/msh"           "$HOME/.local/bin/msh"

# macOS only: if the package came through a browser, clear the quarantine flag
xattr -dr com.apple.quarantine "$PREFIX/$VER" 2>/dev/null || true

"$HOME/.local/bin/mariadb-shell" --version    # must report Ver {{ site.shell_floor }} or newer
```

The plugin finds the shell in `~/.local/bin` whether or not it is on your
`PATH`. Add it to `PATH` anyway, to run `mariadb-shell` yourself in Step 4.

### Windows (PowerShell)

From the folder that holds the package, with `$Pkg` set to your CPU's:

```powershell
$Ver    = '{{ site.shell_floor }}'
$Pkg    = "mariadb-shell-$Ver-windows-x86-64bit"
$Prefix = "$env:LOCALAPPDATA\Programs\mariadb-shell"

New-Item -ItemType Directory -Force -Path $Prefix, "$Prefix\bin" | Out-Null
Unblock-File ".\$Pkg.tar.gz"
tar -xzf ".\$Pkg.tar.gz" -C $Prefix
Rename-Item "$Prefix\$Pkg" $Ver

# The same .cmd shims the online installer writes; the plugin looks for bin\mariadb-shell.cmd
$shim = "@echo off`r`n`"%~dp0..\$Ver\bin\mariadb-shell.exe`" %*`r`n"
foreach ($n in 'mariadb-shell.cmd', 'msh.cmd') {
    Set-Content -Path "$Prefix\bin\$n" -Value $shim -NoNewline -Encoding ascii
}

& "$Prefix\bin\mariadb-shell.cmd" --version    # must report Ver {{ site.shell_floor }} or newer

# Optional: put the shell on your PATH (takes effect in a new terminal)
[Environment]::SetEnvironmentVariable('Path', [Environment]::GetEnvironmentVariable('Path','User') + ";$Prefix\bin", 'User')
```

The names must be exactly these:
`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd` is, besides the
`PATH`, the only place the plugin looks.

<div class="callout callout--warn" markdown="1">
**Windows and pywin32.** If the MCP server dies with
`No module named 'pywintypes'`, the package lacks pywin32 — see
[Troubleshooting]({{ '/get-started/#troubleshooting' | relative_url }}). Offline,
download the pywin32 wheel matching the shell's bundled Python on a connected
machine and install that file instead of running `pip install pywin32`.
</div>

### One shared install instead

Where IT manages software centrally, unpack the shell to a shared location —
`/opt/mariadb-shell/{{ site.shell_floor }}`, say — and put its `bin` folder on
every developer's `PATH`. The plugin accepts any `mariadb-shell` on `PATH` at
{{ site.shell_floor }} or newer.

## Step 3 — Install the plugin from a local folder
{: #step-3-install-the-plugin}

The release archive is a complete plugin marketplace, so Claude Code installs
straight from the unpacked folder. Choose its place for good: Claude Code loads
the plugin from that folder every time it starts.

1. Unpack the archive and give the folder a stable name — the one inside the
   archive is named after the repository and a commit, such as
   `MariaDB-ai-plugins-af5dc47`:

   ```bash
   mkdir -p ~/mariadb && tar -xzf ai-plugins-<version>.tar.gz -C ~/mariadb
   mv ~/mariadb/*-ai-plugins-* ~/mariadb/ai-plugins-<version>
   ```

   On Windows, extract the zip with Explorer or `Expand-Archive`, to
   `C:\Tools\mariadb\ai-plugins-<version>` for example. The folder must contain
   `.claude-plugin\marketplace.json`.
2. Add the folder as a marketplace and install a plugin from it — `dev` for all
   MariaDB skills plus the MCP server, or `sql` for the SQL skills plus the MCP
   server:

   ```bash
   claude plugin marketplace add ~/mariadb/ai-plugins-<version>
   claude plugin install dev@mariadb
   ```

   Inside Claude Code the same is
   `/plugin marketplace add /path/to/ai-plugins-<version>`, then
   `/plugin install dev@mariadb`. On Windows, give the full path.
3. Restart Claude Code.

## Step 4 — Configure the MCP server
{: #step-4-configure-the-mcp-server}

The MCP server can reach no database until it is told which ones it may use.
Run the setup once per machine:

```bash
mariadb-shell -- mcp setup
```

On Windows without the shell on `PATH`, run
`%LOCALAPPDATA%\Programs\mariadb-shell\bin\mariadb-shell.cmd -- mcp setup`.
It asks for the **connections** the agent may use — each password is checked
and kept in the shell's secret store, so the agent never sees it — and the
**allowed paths** it may read and write.
[Get Started]({{ '/get-started/#step-2-configure-the-mcp-server' | relative_url }})
covers both in detail.

Skip the **Migration tooling** option in the setup menu: it downloads the
MySQL-to-MariaDB migration tools from GitHub.

## Step 5 — Verify
{: #step-5-verify}

```bash
claude plugin list    # dev@mariadb, enabled
claude mcp list       # plugin:dev:mariadb: … - ✔ Connected
```

Then, in a Claude Code session, ask:

<div class="prompt" markdown="1">
*List the databases you can connect to.*
</div>

If the server does not connect, run `claude --debug` and look for lines starting
with `mariadb-mcp-launcher:`. `using installed mariadb-shell` or `from PATH`
means the shell was found; `no suitable mariadb-shell found; installing` means it
was not — check the names from Step 2 and that `--version` reports
{{ site.shell_floor }} or newer.

## Sandbox server packages
{: #sandbox-server-packages}

The MCP server deploys throwaway MariaDB instances — sandboxes — for local
testing, and downloads the server version it needs from GitHub. Offline, unpack
the packages by hand where it looks before downloading. It searches, in order:

1. A `mariadbd` on `PATH`.
2. The sandbox server folder: `~/.local/share/mariadb-sandbox-server/<version>/`
   on macOS and Linux (under `$XDG_DATA_HOME` when that is set), or
   `%LOCALAPPDATA%\Programs\mariadb-sandbox-server\<version>\` on Windows.
3. A download from GitHub, which fails offline.

Each version's folder is named with the full version, `11.8.9` say, and holds
`bin/mariadbd` directly — so unpack the package and rename its top-level folder.

### Download links

These are the packages MariaDB Shell {{ site.shell_floor }} knows about, all from
the [v26.10.0 release](https://github.com/mariadb-corporation/mariadb-shell/releases/tag/v26.10.0).
Their checksums are in
[`SERVER_SHA256SUMS`](https://github.com/mariadb-corporation/mariadb-shell/releases/download/v26.10.0/SERVER_SHA256SUMS).

{% assign dl = "https://github.com/mariadb-corporation/mariadb-shell/releases/download/v26.10.0/mariadb-" %}

<div class="table-wrap" markdown="1">

| Platform | MariaDB 11.8 | MariaDB 12.3 | MariaDB 13.1 |
| --- | --- | --- | --- |
| macOS 26+ on Apple silicon | [11.8.9]({{ dl }}11.8.9-macos26-arm-64bit-sandbox.tar.gz) | [12.3.3]({{ dl }}12.3.3-macos26-arm-64bit-sandbox.tar.gz) | [13.1.1]({{ dl }}13.1.1-macos26-arm-64bit-sandbox.tar.gz) |
| macOS 15+ on Intel | [11.8.9]({{ dl }}11.8.9-macos15-x86-64bit-sandbox.tar.gz) | [12.3.3]({{ dl }}12.3.3-macos15-x86-64bit-sandbox.tar.gz) | [13.1.1]({{ dl }}13.1.1-macos15-x86-64bit-sandbox.tar.gz) |
| Linux x86-64, glibc 2.34+ | [11.8.9]({{ dl }}11.8.9-linux-glibc2.34-x86-64bit-sandbox.tar.gz) | [12.3.3]({{ dl }}12.3.3-linux-glibc2.34-x86-64bit-sandbox.tar.gz) | [13.1.1]({{ dl }}13.1.1-linux-glibc2.34-x86-64bit-sandbox.tar.gz) |
| Linux ARM64, glibc 2.34+ | [11.8.9]({{ dl }}11.8.9-linux-glibc2.34-arm-64bit-sandbox.tar.gz) | [12.3.3]({{ dl }}12.3.3-linux-glibc2.34-arm-64bit-sandbox.tar.gz) | [13.1.1]({{ dl }}13.1.1-linux-glibc2.34-arm-64bit-sandbox.tar.gz) |
| Windows x86-64 | [11.8.9]({{ dl }}11.8.9-windows-x86-64bit-sandbox.tar.gz) | [12.3.3]({{ dl }}12.3.3-windows-x86-64bit-sandbox.tar.gz) | [13.1.1]({{ dl }}13.1.1-windows-x86-64bit-sandbox.tar.gz) |
| Windows ARM64 | [11.8.9]({{ dl }}11.8.9-windows-arm-64bit-sandbox.tar.gz) | [12.3.3]({{ dl }}12.3.3-windows-arm-64bit-sandbox.tar.gz) | [13.1.1]({{ dl }}13.1.1-windows-arm-64bit-sandbox.tar.gz) |

</div>

```bash
shasum -a 256 -c SERVER_SHA256SUMS --ignore-missing     # macOS
sha256sum -c SERVER_SHA256SUMS --ignore-missing         # Linux
```

### macOS and Linux

Once per version, with `PKG` and `VER` set to match:

```bash
PKG=mariadb-11.8.9-linux-glibc2.34-x86-64bit-sandbox
VER=11.8.9
ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/mariadb-sandbox-server"

mkdir -p "$ROOT"
tar -xzf "$PKG.tar.gz" -C "$ROOT"
mv "$ROOT/$PKG" "$ROOT/$VER"

# macOS only: clear the quarantine flag, or Gatekeeper may block mariadbd
xattr -cr "$ROOT/$VER" 2>/dev/null || true

"$ROOT/$VER/bin/mariadbd" --version     # Ver 11.8.9-MariaDB … (Development Sandbox)
```

### Windows (PowerShell)

```powershell
$Pkg  = 'mariadb-11.8.9-windows-x86-64bit-sandbox'
$Ver  = '11.8.9'
$Root = "$env:LOCALAPPDATA\Programs\mariadb-sandbox-server"

New-Item -ItemType Directory -Force -Path $Root | Out-Null
Unblock-File ".\$Pkg.tar.gz"
tar -xzf ".\$Pkg.tar.gz" -C $Root
Rename-Item "$Root\$Pkg" $Ver
```

### Using them

An unpacked package is used only when a version is asked for, so name one:

<div class="prompt" markdown="1">
*Deploy a MariaDB 11.8 sandbox on port 3310.*
</div>

`11.8` or `11` picks the newest unpacked release in that series. Without a
version, `sandbox.deploy` uses the `mariadbd` on `PATH`.
`sandbox.list_available_versions` lists everything published for the platform,
unpacked or not — asking for a version that is not unpacked starts a download,
which fails offline.

## What still needs a network
{: #what-still-needs-a-network}

<div class="table-wrap" markdown="1">

| Feature | Offline | Instead |
| --- | --- | --- |
| Sandbox server versions not unpacked | The download fails | Unpack the [sandbox server packages](#sandbox-server-packages), or install MariaDB Server so `mariadbd` is on `PATH` |
| MySQL-to-MariaDB migration tools (`migrator.*`) | Not available — their tooling comes from GitHub | None offline |

</div>

Everything else works offline: the skills, the CLI guard, the SQL language
server for `.sql` files, and the MCP tools against your own databases.

## Rolling out to a team
{: #rolling-out-to-a-team}

Put the unpacked plugin folder at a path that is the same on every machine — a
read-only network share, or a folder your software distribution installs — and
add it to each developer's `~/.claude/settings.json`, or to a repository's
`.claude/settings.json`. Claude Code then offers the plugin with no
`marketplace add`:

```json
{
  "extraKnownMarketplaces": {
    "mariadb": {
      "source": { "source": "directory", "path": "/opt/mariadb/ai-plugins-<version>" }
    }
  },
  "enabledPlugins": { "dev@mariadb": true }
}
```

Each machine still needs MariaDB Shell ([Step 2](#step-2-install-mariadb-shell))
and its own MCP setup ([Step 4](#step-4-configure-the-mcp-server)): connections
and passwords are stored per user.

## Upgrading
{: #upgrading}

1. Download the new ai-plugins release and unpack it beside the old one.
2. Read its `claude/dev-plugin/.mcp.json`: `MARIADB_SHELL_VERSION` there is the
   minimum shell version. Is it newer than yours? Install that shell first, as
   in [Step 2](#step-2-install-mariadb-shell). Your MCP configuration is kept.
3. Point Claude Code at the new folder and restart it:

   ```bash
   claude plugin marketplace remove mariadb
   claude plugin marketplace add ~/mariadb/ai-plugins-<new-version>
   claude plugin install dev@mariadb
   ```

   With `extraKnownMarketplaces`, change the `path` instead.
