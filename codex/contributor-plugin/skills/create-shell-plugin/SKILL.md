---
name: create-shell-plugin
description: Scaffold a MariaDB Shell plugin following project best practices. Use when the user asks to create, scaffold, or add a shell plugin (or a new global object / command / function exposed in the shell), especially in Python using the plugin decorators. Produces a ready-to-load plugin folder with a correctly documented init.py (or init.js).
---

# Create a Shell Plugin

Shell plugins extend the `mariadb-shell` shell with new global objects and functions that
are available from the interactive shell, scripts, and the command-line interface
(CLI). This skill scaffolds a plugin that follows the conventions enforced by the
plugin registrar, so the generated code loads and documents itself correctly on the
first try.

## How plugins are loaded (the contract you must satisfy)

The loader is `Mysql_shell::get_plugins` in [src/mysqlsh/mysql_shell.cc](src/mysqlsh/mysql_shell.cc#L933).

- Each plugin lives in **its own folder** under a `plugins/` search path.
- The folder must contain **exactly one** entry point: `init.py` (Python) **or**
  `init.js` (JavaScript). Having both makes the loader skip the plugin with a warning.
- Search paths, in order (see `Mysql_shell::get_plugins(File_list *)` in
  [src/mysqlsh/mysql_shell.cc](src/mysqlsh/mysql_shell.cc)):
  - `<library_folder>/plugins` — built-in/bundled plugins (skipped if
    `--disable-builtin-plugins` or `MARIADB_SHELL_DISABLE_BUILTIN_PLUGINS=1`).
  - `${MARIADB_SHELL_USER_CONFIG_HOME}/plugins` — per-user (default `~/.mariadb-shell/plugins`
    on Linux/macOS, `%AppData%\MariaDB\mariadb-shell\plugins` on Windows). Skipped if
    `--disable-plugins`. When `MARIADB_SHELL_PLUGINS_PATH` is set (`:`-separated,
    `;` on Windows), its directories are searched instead of this one.
- Loading is recursive: a folder without an init file may contain sub-folders that
  are themselves plugins.
- Plugins are discovered in name order and loaded in passes. A plugin that attaches
  to an object **another plugin** creates (`@plugin(parent="dba.vendor")`, or
  `add_extension_object_member` on a foreign object) declares it in an optional
  `plugin.json` next to `init.py`: `{"requires": ["dba.vendor"]}`, plus an optional
  `providedBy` hint naming the plugin and repository that provide it. The naming
  rules, the loading passes and the hint's shape are in "Load Order and Dependencies"
  of [plugins.md](docs-ref/content/community/mariadb-shell/extending-mariadb-shell/plugins.md).
- The plugin folder name is importable as a Python package, so helper modules go
  beside `init.py` and are imported as `from <folder_name>.<module> import ...`
  (see [python/plugins/debug/](python/plugins/debug/) for the pattern).

Decide **where** to write before scaffolding:
- Bundled / repo-tracked plugin → `python/plugins/<name>/init.py` in this repo.
- Personal / user plugin → `${MARIADB_SHELL_USER_CONFIG_HOME:-~/.mariadb-shell}/plugins/<name>/init.py`.

If the user has not said which, ask. Default to the user config path for one-off
plugins, the repo `python/plugins/` for something meant to ship.

## Always prefer the decorators

Do **not** hand-call `shell.create_extension_object()` /
`shell.add_extension_object_member()` / `shell.register_global()`. The decorators in
[python/packages/mysqlsh/plugin_manager/registrar.py](python/packages/mysqlsh/plugin_manager/registrar.py)
wrap those low-level APIs, derive the help from docstrings, register the function for
JS/Python/CLI/Web, and wrap exceptions cleanly. Use them.

```python
from mysqlsh.plugin_manager import plugin, plugin_function
```

### `@plugin` — register a global (or nested) object

- The **class name** becomes the object name (`myCloud` → `myCloud` global object).
- The **class docstring** becomes its help (first paragraph = brief, rest = details).
- **Inner classes** are registered as nested objects automatically.
- `@plugin(parent="util")` attaches the object as a child of an existing object
  (e.g. extend the built-in `util`). The parent must already exist.
- `@plugin(shell_version_min="9.0.0", shell_version_max="9.9.0")` gates loading by
  shell version; out-of-range plugins are rejected with a clear message.

### `@plugin_function` — register a function on an object

```python
@plugin_function("myCloud.create.instance", cli=True)
def create_instance(name, region="us-east-1", **options):
    ...
```

- The first argument is the **fully-qualified name** in `camelCase`:
  `object[.child].functionName`. The shell auto-exposes it as `functionName` in JS
  and `function_name` (snake_case) in Python — define the Python function in
  snake_case; the camelCase FQN drives the JS/CLI name.
- The object referenced by the FQN must exist (declared via `@plugin` or a parent
  chain). A function can also attach to a nested object declared as an inner class.
- Flags control availability:
  - `shell=True` (default) — available in the interactive shell and scripts.
  - `cli=True` — also exposed as a CLI command (`mariadb-shell -- mycloud create instance ...`).
    `cli=True` requires `shell=True`.
  - `web=True` — registered for web/MRS clients. Can be `web=False`/`True`.
  - `mcp={"group": "<group>", ...}` — also offered as an MCP tool of the MariaDB
    MCP Server (see "Offering a function as an MCP tool" below).
- The decorator wraps the call so tracebacks are logged at `debug` level instead of
  leaking to the user; raise `mysqlsh.Error("message")` for user-facing errors.

### `sql_handler` — intercept SQL statements (advanced)

For plugins that handle custom SQL, use `from mysqlsh.plugin_manager import
sql_handler` with `@sql_handler(name, prefixes)`; the callback is
`callback(session, sql) -> Optional[Result]`. Only reach for this when the user
specifically wants to intercept SQL, not for ordinary commands.

## The docstring grammar (this is parsed — get it right)

`FunctionData._parse_docs` in registrar.py parses docstrings into shell help and
**validates** them. Registration fails loudly if docs are wrong, so follow this
exactly:

- **Brief**: the first line(s) up to the first blank line. Required.
- **Details**: free paragraphs after the brief. Optional. Arbitrary `Section:`
  headers (a line ending in `:`) render as bold sections.
- **Every parameter must be documented, and only real parameters may be documented** —
  a missing or extra entry raises an exception at load time.
- `Args:` section, one entry per parameter:
  ```
  Args:
      name (type): One-line brief, continued indented lines allowed.
  ```
  Types map to shell types: `str`→string, `int`→integer, `bool`→boolean,
  `dict`→dictionary, `list`→array, `object` for session/handles, or omit the
  `(type)` for an untyped/any parameter.
- A parameter with a default value is automatically optional — do not say "optional"
  in the type. Mark a **required dict option** with `(str,required)`.
- For `**options` (or any `dict` parameter), document the keys in a companion
  section:
  - `**options` → `Keyword Args:` section.
  - a named dict parameter `cfg` → `Allowed options for cfg:` section.
  Nested dict options get their own `Allowed options for <optName>:` section.
- Bullet lists use sphinx syntax: lines starting with `* ` become `@li` items.

A correct multi-section example lives in
[unittest/scripts/auto/py_shell/scripts/plugin_decorator_norecord.py](unittest/scripts/auto/py_shell/scripts/plugin_decorator_norecord.py) —
consult it for edge cases (required dict params, nested options, web-only functions).

## Offering a function as an MCP tool

When the user wants agents to call a function through the MariaDB MCP Server
(`mcp_plugin` in mariadb-shell-plugins), pass `mcp=` to `@plugin_function`. The
plugin imports neither mcp_plugin nor the MCP SDK; the server reads the shell's
registry (`registrar.get_registry()`, each entry's `.mcp`) when it starts.

```python
@plugin_function("orders.listOpen", mcp={"group": "orders", "readOnly": True})
def list_open(customer, limit=20, session=None):
    ...
```

- Keys: `group` (required; lower case, digits, `_`; not a built-in group such
  as `db`), `name` (default: the function name in snake_case), `readOnly`,
  `destructive`, `paths` (parameters holding file paths, checked against the
  server's allowed paths), `task` (run as a background task), `gui` (only on a
  `--gui` server). The shell only checks that `mcp` is a dict (`mcp=True` is
  refused) and stores it as given, as it does `web=`; mcp_plugin's
  `check_definition` checks the keys when the server starts, and a tool with a
  mistake is not served (the server log says why). Have the user run the
  server once to see such a mistake.
- A `session` parameter is filled in by the server: the tool takes the
  `connection_id` from `db.connect` instead, and is served only with the `db`
  group. Keep `session=None` with a fallback to `shell.get_session()`, so the
  function still works in the shell.
- With `"task": True`, a `task` parameter receives the background task
  (`task.progress(current, total)`, `task.check_cancelled()`); the return
  value is the task's result.
- Parameters may not be called `ctx`, `connection_id`, `options` or start with
  `_`; `*args` is not allowed. `**options` is published as one `options`
  object, documented by `Keyword Args:`.
- Return plain values; a `run_sql()` result is sent as its rows. Raise
  `mysqlsh.Error` to refuse a call.
- Set `@plugin(shell_version_min=...)` to the first shell with `mcp=`.
- Tell the user the group is served only when named in
  `mcp start-server --functionGroups` or allowed with
  `mcp setup --extensionGroups=<group>`.

## Accessing shell facilities from a plugin

```python
from mysqlsh import globals          # globals.shell, globals.session, globals.db
from mysqlsh import Error, DBError, mysql
```

- `globals.shell` — the shell global object (`parse_uri`, `open_session`,
  `get_session`, `log`, `create_extension_object`, ...).
- `globals.session` — the currently active session (may be `None`).
- Raise `mysqlsh.Error(...)` for clean user errors; the decorator suppresses the
  traceback and logs it at debug level.

## Workflow when asked to create a plugin

1. **Clarify the shape** if not already clear: object name(s) and hierarchy, the
   functions and their parameters, whether it extends an existing object (`parent=`),
   whether CLI/web exposure is wanted, and Python vs JavaScript (default Python —
   that is where the decorators live and what the user asked for).
2. **Pick the target path** (repo `python/plugins/<name>/` vs user config
   `plugins/<name>/`). Ask if ambiguous.
3. **Write `init.py`** using the template below. One `@plugin` class per object,
   `@plugin_function` per command, fully documented docstrings.
4. **Split helpers** into sibling modules (`<name>/<helper>.py`) imported as
   `from <name>.<helper> import ...` when the logic is non-trivial; keep `init.py`
   focused on registration.
   If the plugin extends an object created by another plugin, also write
   `<name>/plugin.json` with `{"requires": ["<that.object>"]}` so it loads after it.
5. **Mirror the project license header** at the top of every file — copy the GPLv2
   header used by existing plugins in [python/plugins/debug/init.py](python/plugins/debug/init.py).
6. **Tell the user how to try it**: it loads on the next `mariadb-shell` start; verify with
   `\? <object>` (help), call it from Python, or `mariadb-shell -- <object> <function> ...`
   for CLI. If running from the repo build, plugins under `python/plugins/` are
   bundled into the build's share path.

## Template (Python)

```python
# <GPLv2 license header — copy from python/plugins/debug/init.py>

from mysqlsh.plugin_manager import plugin, plugin_function
from mysqlsh import globals, Error


@plugin
class myPlugin:
    """Short brief shown in `\\? myPlugin`.

    Longer details paragraph describing what the plugin does. Supports
    bullet lists:

    * does this
    * and that
    """

    class sub:
        """A nested object: myPlugin.sub."""
        pass


@plugin_function("myPlugin.doThing", cli=True)
def do_thing(target, retries=3, **options):
    """One-line brief for the command.

    Optional longer description of the behavior.

    Args:
        target (str): What to act on.
        retries (int): Number of attempts. Defaults to 3 (optional).
        **options (dict): Optional arguments.

    Keyword Args:
        force (bool): Skip confirmation. Default false.
        label (str): Human-readable label.
    """
    session = globals.shell.get_session()
    if session is None:
        raise Error("This command requires an active session.")
    # ... implementation ...
```

## JavaScript option

If the user wants JS, create `init.js` (never alongside an `init.py`). There are no
decorators in JS — register explicitly via the shell API:
`shell.createExtensionObject()`, `shell.addExtensionObjectMember(obj, name, fn, {...help...})`,
and `shell.registerGlobal(name, obj, {...help...})`. See
[unittest/scripts/auto/js_shell/scripts/extensible_objects_norecord.js](unittest/scripts/auto/js_shell/scripts/extensible_objects_norecord.js)
for the member/help dictionary shape. Prefer Python unless the user needs JS.
