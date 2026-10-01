---
description: >-
  Install the MariaDB AI Plugins into Codex from the MariaDB plugin
  marketplace.
---

# Codex

## Install the Plugin

Add the MariaDB marketplace and install the `dev` plugin with the Codex CLI:

```bash
codex plugin marketplace add mariadb/ai-plugins
codex plugin add dev@mariadb
```

To install a different variant, replace `dev` with `sql` or `contributor`. See [Plugin Variants](../plugin-variants.md).

The `/plugins` command in Codex lets you browse and enable plugins interactively. Because it takes no arguments, you must add the marketplace with the CLI.

## Configure the MCP Server

Codex starts the MCP server directly from the plugin's configuration, so you don't need to register it separately. Before the agent can use the server, you must configure the connections and directories it may access. See [Configuring the MCP Server](../configuring-the-mcp-server/README.md).

## Register the MCP Server Manually

If the MCP server doesn't start, register it with the script included in the plugin:

{% tabs %}
{% tab title="Linux and macOS" %}
```bash
codex/dev-plugin/scripts/setup-codex-mcp.sh
```

To unregister the server, add `--remove`.
{% endtab %}

{% tab title="Windows" %}
```
codex\dev-plugin\scripts\setup-codex-mcp.cmd
```

To unregister the server, add `--remove`.
{% endtab %}
{% endtabs %}

## Verify the Installation

Run `/plugins` in Codex to check that the plugin is enabled.
