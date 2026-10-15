---
name: mariadb-migrator-configure
description: "Write the MySQL-to-MariaDB migrator's config/migration.yaml with migrator.set_config — the rules that get a configuration refused (every named account must be a configured MCP connection, SRC_PORT/TGT_PORT always explicit, no password key ever, string values only), the keys each mode requires, the useful optional keys, and what MIGRATE_APP_USERS does to accounts and grants. Use when configuring a migration, when set_config was refused, when a password or app-user migration needs setting up, or when correcting a configuration with merge=True. Read mariadb-migrator first for the tools and preconditions."
---

# Migration — Writing the Configuration

`migrator.set_config` writes the tooling's `config/migration.yaml`, following its
own `config/migration.yaml.example` (the returned `example_path` is the full key
reference — read it when you need a key not listed here).

Pick the mode first (`mariadb-migrator-modes`): it decides which keys below are
required.

## The rules that get configurations refused

**Every account you name must be a configured connection.** The tooling's
accounts are paired with a side's host and port to compose a URI, and each has to
resolve against `db.list_connections`:

| Account key | Resolved as |
| --- | --- |
| `SRC_ADMIN_USER` | `<user>@<SRC_HOST>:<SRC_PORT>` |
| `SRC_USER` | `<user>@<SRC_HOST>:<SRC_PORT>` |
| `TGT_ADMIN_USER` | `<user>@<TGT_HOST>:<TGT_PORT>` |
| `TGT_USER` | `<user>@<TGT_HOST>:<TGT_PORT>` |
| `REPL_USER` | `<user>@<SRC_HOST>:<SRC_PORT>` — the replication user lives on the **source** |

- **Always set `SRC_PORT` and `TGT_PORT` explicitly.** They are half of the URI
  the password is looked up under. An omitted port is read as 3306, so on any
  other port the lookup silently finds nothing.
- **Naming a host with no account is refused too** (`SRC_HOST` with neither
  `SRC_ADMIN_USER` nor `SRC_USER`). There would be nothing to check.
- Validated on the **merged** result, so two `merge=True` calls cannot assemble a
  forbidden connection between them — and **validated again when a run starts**,
  so a connection removed with `mcp.setup` stops migrations already configured
  against it.

**Never set a password.** `SRC_PASS`, `SRC_ADMIN_PASS`, `TGT_PASS`,
`TGT_ADMIN_PASS` and `REPL_PASS` are **refused** if you give them a value. Set
the matching user/host/port fields and the password follows on its own. The
returned `passwords_from` tells you which connection each will be read from, and
never the secret itself.

**Values are strings.** Numbers and booleans are converted for you (a boolean
becomes the `"1"`/`"0"` the tooling reads). A list or a dict is refused — there
is no string it should silently become.

**Use `merge=True` for a correction**, not a fresh full write — you keep the keys
you got right, and the merged result is validated as a whole anyway. Then `plan`
again.

## Keys each mode requires

Beyond the connection fields above:

| Mode | Also required |
| --- | --- |
| `one_step`, `two_step`, `binlog` | `SRC_DB` (one database) **or** `SRC_DBS` (comma-separated) |
| `binlog` | `REPL_USER` (and its configured connection on the source) |
| `staged` | `STAGED_PHASE` (`dump_and_load` default / `dump_only` / `load_only`); `SRC_DB`/`SRC_DBS` unless `load_only`; `STAGED_DUMP_DIR` when `load_only` |

Useful optional keys: `SRC_SSL_MODE` (`DISABLED` | `REQUIRED` | `VERIFY_CA` |
`VERIFY_IDENTITY`), `ANALYZE_TARGET` (refresh optimizer statistics after the
load, default on), `MIGRATE_APP_USERS` + `APP_USER_DEFAULT_PASSWORD` +
`APP_USER_PWD_EXPIRE`, `ALLOW_TARGET_DB_OVERWRITE`, and the `STAGED_*` family
(`STAGED_COMPRESS`, `STAGED_PARALLEL`, `STAGED_LOAD_PARALLEL`, `STAGED_PV`).

Mode 2 also needs `SQLINESDATA_BIN` unless `mariadb-mtk` is on `PATH` — see
`mariadb-migrator-modes`.

## If you turn on `MIGRATE_APP_USERS`

Two things about migrated accounts produce "the migration succeeded but nobody
can log in", and both are worth raising before the run rather than after.

**`caching_sha2_password` hashes do not survive text transport — but the
tool's own migration path avoids this.** The hash contains non-printable
binary bytes that corrupt when passed through a terminal or embedded in a
text literal. `MIGRATE_APP_USERS` doesn't do that: it moves the hash via
`HEX()` on the source, then `JSON_SET`/`UNHEX` against `mysql.global_priv`
on the target, so the automated path is safe as-is — don't raise this as a
caveat against turning the flag on. It matters only as a **diagnostic**: if
someone reports a migrated account failing and they separately hand-copied
a hash out of a query result (outside the tool, e.g. to debug or re-apply
it manually), that hand-copy is the bug and the hash needs redoing — not the
grants, and not the migration itself. (MDEV-38524 tracks the upstream
ergonomics fix for that manual case.)

**`caching_sha2_password` needs TLS or RSA key exchange to authenticate at all.**
With neither available the server returns a generic access-denied, so a
completely correct hash looks like a wrong password. Check the connection's TLS
state before concluding anything about the credential.

**Review the account list before accepting it.** Infrastructure accounts —
`repl_user`, `replicator`, `pmm_*` and the like — are not deny-listed yet, so
they classify into the application-user buckets and get migrated as though they
were app users. Exclude monitoring and replication accounts by hand.

**Read the dropped-grant bucket entry by entry.** It currently mixes two
unrelated things: privileges MySQL has and MariaDB does not (dynamic
privileges), and grants that failed only on role-grant ordering. The second kind
is often re-appliable as-is, so reporting the bucket as one number understates
what can be recovered.

## A complete mode 1 configuration

```text
migrator.set_config(
    mode="one_step",
    env={
        # Source — a configured connection: root@127.0.0.1:3307
        "SRC_HOST": "127.0.0.1",
        "SRC_PORT": "3307",
        "SRC_ADMIN_USER": "root",
        "SRC_USER": "root",
        "SRC_DBS": "shop,billing",
        "SRC_SSL_MODE": "DISABLED",
        # Target — a configured connection: root@127.0.0.1:3308
        "TGT_HOST": "127.0.0.1",
        "TGT_PORT": "3308",
        "TGT_ADMIN_USER": "root",
        "TGT_USER": "root",
        # Only when migrating as root is genuinely intended.
        "ALLOW_ROOT_USERS": "1",
        "MIGRATE_APP_USERS": "0",
        "ANALYZE_TARGET": "1",
    },
)
```

No `*_PASS` key appears. Check the returned `connections` mapping: every account
you named must be there, pointing at the connection you expected.

## See Also

- `mariadb-migrator` — the overview: tools, preconditions, modes at a glance.
- `mariadb-migrator-discovery` — where the connection names come from.
- `mariadb-migrator-modes` — which mode needs which keys, and each mode's gates.
- `mariadb-migrator-run` — `plan` the configuration, then run it.
- `mariadb-migrator-troubleshooting` — every refusal message and its fix.
