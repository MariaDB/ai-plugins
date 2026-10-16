# Copyright (c) 2026, MariaDB plc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License, version 2.0,
# as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See
# the GNU General Public License, version 2.0, for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

"""MariaDB CLI guard for Hermes Agent.

Keeps the agent from using the MariaDB/MySQL command-line clients for what the
mariadb MCP server's tools do. A client run from a shell needs the password on
its command line or in its environment, where it lands in the process list, in
logs and in the transcript the model provider sees. A connection opened through
the MCP server reads its password from the operating system's secret store.

Only five clients are looked at, and each only for what a tool covers:

- ``mariadb``, ``mysql``: running SQL -> db.execute_sql(_script)
- ``mariadb-shell``, ``mysqlsh``: SQL mode -> db.execute_sql(_script), and
  ``-- <object> <method>`` calls -> the matching tool
- ``mariadb-dump``: piped into another client -> util.copy_*

Everything else - --version and --help, Python or JavaScript mode, a dump
written to a file, ``-- mcp setup``, an API call no tool wraps - is let
through, so the agent keeps every feature the tools do not have yet.

Two parts: a system-prompt section that says to use the MCP tools, and a
``pre_tool_call`` hook that blocks a ``terminal`` call using a client for such a
task, naming the tool to call instead. Starting Hermes with
``MARIADB_PLUGIN_ALLOW_CLI=1`` turns both off.

A separate package from ``mariadb-dev`` / ``mariadb-sql`` because Hermes only
runs hooks from a Python plugin, and a folder with a ``plugin.yaml`` is never
read as a portable package (skills and MCP server). ``find_client`` is a port
of the bash hook the Claude Code and Codex plugins ship
(``hooks/mariadb-cli-guard.sh``); ``tests/cli-guard-cases.json`` at the
repository root holds the cases every port must agree on.
"""

import os
import re

ALLOW_ENV = "MARIADB_PLUGIN_ALLOW_CLI"

# The `-- <object> <method>` calls an MCP tool wraps, named like the tool.
_COVERED_API = {
    "util.dump_instance", "util.dump_schemas", "util.dump_tables",
    "util.export_table", "util.load_dump", "util.import_table",
    "util.copy_instance", "util.copy_schemas", "util.copy_tables",
    "sandbox.deploy", "sandbox.start", "sandbox.stop", "sandbox.kill",
    "sandbox.delete",
    "msm.create_project", "msm.get_project_information",
    "msm.set_development_version", "msm.get_released_versions",
    "msm.get_last_released_version", "msm.get_last_deployment_version",
    "msm.prepare_release", "msm.get_sql_content_from_section",
    "msm.set_section_sql_content", "msm.generate_deployment_script",
    "msm.get_deployment_script_versions", "msm.deploy_schema",
    "mrs.dump_service", "mrs.load_service", "mrs.dump_service_project",
    "mrs.load_service_project", "mrs.load_content_set", "mrs.dump_audit_log",
    "mrs.dump_sdk_service_files",
}

# What runs a command rather than being one, besides VAR=value and -options.
_WRAPPERS = {
    "sudo", "doas", "env", "command", "exec", "nohup", "time", "nice", "xargs",
    "do", "then", "else", "elif", "if", "while", "until", "!",
}

# Shells, and eval: their string argument is a command line of its own.
_SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "eval"}

_INFO_FLAGS = {"--version", "-V", "--help", "-?", "-I", "--print-defaults"}

_SEPARATORS = set(";&|(){}`\n")

_USE_SQL_TOOLS = (
    "run the SQL with db.connect and db.execute_sql, or db.execute_sql_script "
    "(it takes a file_path for a .sql file), instead"
)
_USE_COPY_TOOLS = (
    "copy between servers with util.copy_instance, util.copy_schemas or "
    "util.copy_tables instead (a dump written to a file is fine)"
)

SYSTEM_PROMPT_RULE = (
    "MariaDB: work with databases through the mariadb MCP server's tools - SQL "
    "with db.connect, db.execute_sql and db.execute_sql_script, local test "
    "servers with sandbox.*, dumps, loads and copies with util.* - rather than "
    "by running mariadb, mysql, mariadb-shell, mysqlsh or mariadb-dump from the "
    "terminal, which is blocked where a tool covers the task. A client is fine "
    "for what no tool covers. Never ask for, or put into a command, a database "
    "password; deploy a sandbox with a freshly generated random password, which "
    "is stored with its connection. If a server is not in db.list_connections, "
    "ask the user to add it with `mariadb-shell -- mcp setup`."
)


def block_reason(finding):
    """What the model is told instead of the command's output.

    Args:
        finding: (client, what to do instead), as find_client returns it.
    """
    client, use = finding
    return (
        f"Blocked: `{client}` does something the mariadb MCP server's tools do, "
        "and a client run from a shell puts database credentials on a command "
        "line, in the process list, in logs and in this conversation. Use the "
        f"MCP tools: {use}. Never ask for or pass a database password: open a "
        "server with db.connect, and if it is not in db.list_connections, ask "
        "the user to add it with `mariadb-shell -- mcp setup`. What no MCP tool "
        "covers is not blocked. If the user wants you to run the clients "
        f"anyway, they can start the agent with {ALLOW_ENV}=1."
    )


def _is_info_flag(arg):
    return arg in _INFO_FLAGS or arg.startswith("--help=")


def _snake_case(method):
    """kebab-case and camelCase both name the same method."""
    return re.sub(r"([A-Z])", r"_\1", method.replace("-", "_")).lower()


def _check_shell(name, args):
    mode = file = object_ = method = ""
    api = False
    j = 0
    while j < len(args):
        arg = args[j]
        j += 1
        if api:
            if not arg.startswith("-"):
                if not object_:
                    object_ = arg
                elif not method:
                    method = arg
            continue
        if _is_info_flag(arg):
            return None
        if arg == "--":
            api = True
        elif arg in ("--sql", "--sqlc", "--sqlx"):
            mode = "sql"
        elif arg in ("--py", "--python"):
            mode = "py"
        elif arg in ("--js", "--javascript"):
            mode = "js"
        elif arg in ("-f", "--file"):
            file = args[j] if j < len(args) else ""
            j += 1
        elif arg.startswith("--file="):
            file = arg[len("--file="):]

    if api:
        if not method:
            return None
        tool = f"{object_}.{_snake_case(method)}"
        if tool in _COVERED_API:
            return (name, f"call the MCP tool {tool} instead")
        return None

    if not mode:
        for extension in ("sql", "py", "js"):
            if file.endswith("." + extension):
                mode = extension
    # MariaDB Shell starts in SQL mode, MySQL Shell in JavaScript.
    if not mode:
        mode = "sql" if name == "mariadb-shell" else "js"
    return (name, _USE_SQL_TOOLS) if mode == "sql" else None


def _check_words(words, piped_from):
    """One simple command: (the command it runs, the finding or None)."""
    i = 0
    while i < len(words):
        word = words[i]
        # `command -v NAME` looks a command up rather than running it.
        if word == "command" and i + 1 < len(words) and words[i + 1] in ("-v", "-V"):
            return "", None
        if "=" in word or word.startswith("-") or word in _WRAPPERS:
            i += 1
            continue
        break
    if i >= len(words):
        return "", None

    name = words[i].replace("\\", "/").rsplit("/", 1)[-1]
    if name.endswith(".exe"):
        name = name[:-4]
    args = words[i + 1:]

    if name in _SHELLS:
        for arg in args:
            if not arg.startswith("-"):
                found = find_client(arg)
                if found:
                    return name, found
        return name, None
    if name in ("mariadb", "mysql"):
        if any(_is_info_flag(arg) for arg in args):
            return name, None
        if piped_from == "mariadb-dump":
            return name, (f"mariadb-dump | {name}", _USE_COPY_TOOLS)
        return name, (name, _USE_SQL_TOOLS)
    if name in ("mariadb-shell", "mysqlsh"):
        return name, _check_shell(name, args)
    # mariadb-dump on its own is fine: no tool writes a .sql dump.
    return name, None


def find_client(line):
    """Returns (client, what to do instead) for a command line, or None.

    Splits it into simple commands at the shell's separators outside quotes,
    and each of those into words with the quotes removed; $(...) and `...`
    start a command of their own, inside double quotes too.
    """
    n = len(line)
    words, word, have_word, quote, piped_from = [], "", False, "", ""

    def end_command():
        nonlocal words, word, have_word
        if have_word:
            words.append(word)
        result = _check_words(words, piped_from) if words else ("", None)
        words, word, have_word = [], "", False
        return result

    k = 0
    while k < n:
        c = line[k]
        if quote:
            if c == quote:
                quote = ""
            elif quote == '"' and c == "\\":
                k += 1
                word += line[k:k + 1]
            elif quote == '"' and (line.startswith("$(", k) or c == "`"):
                # A substitution runs even inside double quotes: check it.
                if c == "`":
                    start = end = k + 1
                    while end < n and line[end] != "`":
                        end += 1
                else:
                    start = end = k + 2
                    depth = 1
                    while end < n and depth > 0:
                        if line[end] == "(":
                            depth += 1
                        elif line[end] == ")":
                            depth -= 1
                        if depth > 0:
                            end += 1
                found = find_client(line[start:end])
                if found:
                    return found
                k = end
            else:
                word += c
        elif c in ("'", '"'):
            quote = c
            have_word = True
        elif c == "\\":
            k += 1
            word += line[k:k + 1]
            have_word = True
        elif c in (" ", "\t"):
            if have_word:
                words.append(word)
            word, have_word = "", False
        elif c in _SEPARATORS:
            name, found = end_command()
            if found:
                return found
            # A single | hands this command's output to the next one; || and
            # every other separator do not.
            pipe = c == "|" and line[k + 1:k + 2] != "|" and line[k - 1:k] != "|"
            piped_from = name if pipe else ""
        elif c == "$" and line[k + 1:k + 2] == "(":
            _, found = end_command()
            if found:
                return found
            piped_from = ""
            k += 1
        else:
            word += c
            have_word = True
        k += 1
    return end_command()[1]


def _pre_tool_call(tool_name=None, args=None, **_kwargs):
    # Hermes blocks the call when a pre_tool_call hook raises, so nothing
    # unexpected may escape: a broken guard must not stop unrelated work.
    try:
        if tool_name != "terminal" or not isinstance(args, dict):
            return None
        command = args.get("command")
        if not isinstance(command, str):
            return None
        finding = find_client(command)
    except Exception:  # noqa: BLE001
        return None
    if finding:
        return {"action": "block", "message": block_reason(finding)}
    return None


def register(ctx):
    if os.environ.get(ALLOW_ENV) == "1":
        return
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    ctx.register_system_prompt_section("mariadb-guard.db-access", SYSTEM_PROMPT_RULE)
