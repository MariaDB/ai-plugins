---
description: >-
  Install the MariaDB AI Plugins into Pi as a Pi package, with the
  pi-mcp-adapter extension for MCP support.
---

# Pi

Pi has neither a plugin marketplace nor built-in MCP support. You therefore install the MariaDB AI Plugins repository as a Pi package, and add MCP support with the community extension [`pi-mcp-adapter`](https://pi.dev/packages/pi-mcp-adapter). Only the `dev` plugin is available for Pi.

## Install the MCP Adapter

Install the adapter once, if you don't have it yet:

```bash
pi install npm:pi-mcp-adapter
```

## Install the Plugin

Install the plugin from GitHub:

```bash
pi install git:github.com/mariadb/ai-plugins
```

Alternatively, from a local checkout of the repository, run this at the repository root:

```bash
pi install .
```

Restart Pi, or run `/reload`, to load the skills and the extension.

## Register the MCP Server

Register the MariaDB MCP server with the adapter from inside Pi:

```
/mariadb-mcp-setup
```

This writes the global `~/.config/mcp/mcp.json`. To register the server for the current project only, in `./.mcp.json`, add `--project`.

Then run `/mcp reconnect mariadb`, or restart Pi. While the server isn't registered, the extension prints a reminder at the start of each session.

## Configure the MCP Server

Registering the server with Pi doesn't configure which connections and directories it may access. For that step, see [Configuring the MCP Server](../configuring-the-mcp-server/README.md).

{% hint style="warning" %}
A project-local Pi package must be approved at run time with `--approve`. Without it, the package is configured but never loaded.
{% endhint %}
