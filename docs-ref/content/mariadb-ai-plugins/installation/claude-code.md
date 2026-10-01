---
description: >-
  Install the MariaDB AI Plugins into Claude Code from the MariaDB plugin
  marketplace.
---

# Claude Code

## Install the Plugin

Add the MariaDB marketplace and install the `dev` plugin from inside Claude Code:

```
/plugin marketplace add mariadb/ai-plugins
/plugin install dev@mariadb
```

To install a different variant, replace `dev` with `sql` or `contributor`. See [Plugin Variants](../plugin-variants.md).

## Configure the MCP Server

The `dev` and `sql` plugins register the MCP server with Claude Code automatically. Before the agent can use the server, you must configure the connections and directories it may access. See [Configuring the MCP Server](../configuring-the-mcp-server/README.md).

## Verify the Installation

Run `/plugin` to list the installed plugins, and `/mcp` to check that the `mariadb` MCP server is connected.

## Update or Remove the Plugin

Use `/plugin` to update or uninstall the plugin. Removing the plugin doesn't remove MariaDB Shell or its configuration in `~/.mariadb-shell`.
