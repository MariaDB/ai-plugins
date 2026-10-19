# MariaDB guard plugin for Hermes Agent

Version **26.10.4**

A companion to the [`mariadb-dev`](../dev-plugin/README.md) and
[`mariadb-sql`](../sql-plugin/README.md) plugins. It stops the agent from using
the MariaDB and MySQL command-line clients for what the `mariadb` MCP server's
tools do, so that work goes through the MCP server.

## Why

A command-line client run from the agent's terminal needs the password on its
command line (`-p<password>`) or in its environment. From there it reaches the
process list, logs, and the conversation the model provider sees. A connection
opened through the MCP server reads its password from the operating system's
secret store, so the agent never sees a password at all.

To give the agent a server, configure it in the MCP server yourself, either
interactively with `mariadb-shell -- mcp setup` or with its
[command-line options](https://mariadb.com/docs/tools/community/mariadb-shell/mcp-server/automated-setup).
For a local test server, the agent deploys a sandbox with a random root password
it generates; the password is stored with the sandbox's connection.

## What it does

It looks at only five clients, and each only where an MCP tool does the job:

| Client | Blocked when | Use instead |
| --- | --- | --- |
| `mariadb`, `mysql` | it runs SQL | `db.execute_sql`, `db.execute_sql_script` |
| `mariadb-shell`, `mysqlsh` | it runs SQL (SQL mode) | `db.execute_sql`, `db.execute_sql_script` |
| `mariadb-shell`, `mysqlsh` | it calls `-- <object> <method>` that a tool wraps, such as `-- util dump-schemas` | the matching tool, here `util.dump_schemas` |
| `mariadb-dump` | its output is piped into another client | `util.copy_instance`, `util.copy_schemas`, `util.copy_tables` |

- A blocked `terminal` call gets an explanation naming the tool to use instead.
  A client is caught behind a path, `env`, a pipe, `&&`, `sh -c "..."` or
  `$(...)`.
- Everything else runs: `--version` and `--help`, Python or JavaScript mode, a
  dump written to a file, `mariadb-shell -- mcp setup`, an API call no tool
  wraps, and every other client. The agent keeps the features the MCP tools do
  not have yet.
- A system-prompt section says the same before the first tool call.

## Installation

Hermes runs hooks only from a Python plugin, and a Python plugin cannot also
carry skills and an MCP server. So the guard is a package of its own, installed
next to `mariadb-dev` (or `mariadb-sql`):

```sh
hermes plugins install mariadb/ai-plugins#hermes/guard-plugin --enable
```

Then start a new Hermes session.

## Turning it off

If you want the agent to run the clients itself, start Hermes with
`MARIADB_PLUGIN_ALLOW_CLI=1` in its environment, or run
`hermes plugins disable mariadb-guard`. The model cannot turn it off: the
variable is read from Hermes' own environment, not from the command the model
runs.

## Limits

The guard reads the command the way a shell would split it, but it does not
run it. A command built at run time (`$(echo mariadb) -e ...`), or a client
started from `execute_code` instead of `terminal`, is not caught. The guard is a
safety net, not a sandbox; the MCP server's instructions and the plugin's
system-prompt section are what steer the agent in the first place.

## License

GPL-2.0, see [LICENSE](LICENSE).
