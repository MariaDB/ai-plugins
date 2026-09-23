---
order: 4
slug: sandbox-lifecycle
title: "Throwaway MariaDB servers on demand"
description: >-
  Ask for a real MariaDB instance, use it, and throw it away — no Docker, no
  container runtime, no administrator rights. The safety net that lets an agent
  try a destructive change before it touches anything real.
level: beginner
duration: "20 min"
area: sandbox
tools: ["sandbox.list_available_versions", "sandbox.deploy", "sandbox.start", "sandbox.stop", "sandbox.kill", "sandbox.delete", "sandbox.version"]
skills: ["mariadb-features"]
path_label: "Operate and Optimize, Step 1"
prerequisites:
  - "A plugin installed and `mariadb-shell -- mcp setup` run once."
  - "Nothing else. A sandbox needs no MariaDB Server on the machine — it downloads one if it has to."
---

The single most useful thing about giving an agent database tools is also the
scariest, and sandboxes are the answer to both. The agent can create and destroy
complete MariaDB server instances in a folder, so "try this migration somewhere
harmless first" is a real option rather than a wish.

<div class="prompt" markdown="1">
*Spin up a MariaDB sandbox on port 3310, tell me what version it is, and leave it
running.*
</div>

## What a sandbox actually is

A directory with a data directory and a config file in it, plus a running
`mariadbd`. No image, no container daemon, no root requirement — and cleanup is
a directory removal.

The port doubles as the instance's name. Once you have said 3310, "the sandbox
on 3310" is enough to refer to it for the rest of the session.

That server does **not** have to be installed on the machine. One is resolved
from three places, **in this order**:

1. **The `PATH`.** A machine that already satisfies the request downloads
   nothing.
2. **Versions already downloaded** from an earlier sandbox.
3. **The published index** — fetched, checksum-verified and unpacked.

That order is why the same request can take two seconds or two minutes. The
agent will tell you which happened, because it is the difference between "this
is slow" and "this is fine".

<div class="callout callout--tip" markdown="1">
**The `PATH` is deliberately not held to "newest".** It holds one server, and
the only question is whether it satisfies what you asked for. A machine with
11.8.9 installed will not fetch 11.8.10 because you said `11`. Already-downloaded
copies and the index *do* take the newest match.
</div>

## Ask what versions are available

<div class="prompt" markdown="1">
*Which MariaDB versions can you deploy here? Show me every 11.8 release, not
just the newest.*
</div>

One call covers both halves of that question — the agent just varies what it
asks for:

```text
sandbox.list_available_versions()               → the newest patch of each series
sandbox.list_available_versions(series="11.8")  → every 11.8 patch release
```

Only versions with a package built for **your** platform are listed, and
anything listed can always be deployed — if it is not on the machine already, it
is fetched.

<div class="callout" markdown="1">
**That list is a static index inside the plugin, not a live lookup.** What a
given plugin version can install is therefore reproducible and reviewable in a
diff, and listing costs no network. The flip side: a newly published server
release arrives with a plugin update, not on its own.
</div>

## What you can ask for when you deploy one

A port is the whole of the required request — the agent picks a root password
and registers it with the connection, so you never have to invent or remember
one. Everything else is worth knowing only because it is occasionally exactly
what you need:

- **A version.** "the newest 11.8", "11.8.9 exactly", or "anything on 11" —
  each level you leave off is filled in with the newest release below it.
- **Somewhere other than the default folder**, if you want the instance to live
  in your project directory. It has to be a directory the MCP server was given
  access to.
- **Non-default server settings**, which is how you test a configuration change
  before making it anywhere real.
- **TLS on**, which needs `openssl` on the machine. It is off by default, and
  off is the right choice unless TLS is the thing you are testing.
- **A root password of your choosing**, which matters only when something other
  than the agent has to log in — a command-line client, a GUI, an application
  you are pointing at the sandbox.

<div class="callout callout--warn" markdown="1">
**Do not ask for a blank password.** It is the one value that is accepted and
then breaks everything: the connection gets registered, nothing can open it, and
the failure reads like a permissions problem rather than a password problem.
Either say nothing and let the agent choose one, or give it a real one.
</div>

On a successful deploy the connection `root@127.0.0.1:<port>` is **registered
automatically**, password and all. You do not have to configure anything for the
agent to be able to use the server it just made.

<div class="callout callout--warn" markdown="1">
**Two other ways a deploy goes wrong, and what each looks like**

- **It hangs.** The sandbox directory is not on the allowed-paths list, and the
  path guard is waiting for a confirmation a headless agent cannot give. Run
  `mariadb-shell -- mcp setup` and add the directory.
- **It fails on TLS.** You asked for TLS on a machine with no `openssl`. Ask
  again without it.
</div>

Because a sandbox listens on all interfaces with a `root` account that can
connect from anywhere, it is a development tool. Do not leave one running on a
machine on an untrusted network.

## Stop, restart, delete

<div class="prompt" markdown="1">
*Stop the sandbox on 3310 — I want to come back to this data tomorrow.*
</div>

Stopping keeps the data; restarting brings the same instance back up untouched.
Deleting removes the directory for good. Three rules are worth knowing because
they explain the errors:

- **A sandbox cannot be deleted while it is running.** If a delete complains,
  the stop did not land.
- **Restarting is not redeploying.** Redeploying onto a port that already has an
  instance is an error rather than an overwrite, which is deliberate — it means
  you cannot silently destroy yesterday's data by repeating a prompt.
- **A wedged server can always be forced down.** If a graceful stop fails, the
  agent falls back to killing it, and then the delete works.

<div class="callout callout--tip" markdown="1">
**Always ask for the cleanup in the same breath as the creation.** An agent whose
run times out leaves the server running and the directory behind, and the next
deploy on that port then fails for reasons that look unrelated. Put the teardown
in the instruction: *"…and delete the sandbox when you are done, even if a step
fails."*
</div>

## Check what you actually got

Never take the version from the request — take it from the server:

<div class="prompt" markdown="1">
*What version and vendor is the server on 3310 actually running?*
</div>

The agent reads both straight off the running server:

```text
sandbox.version(port=3310)   → "11.8.x"
sandbox.vendor(port=3310)    → "MariaDB"
```

There is a vendor to ask about because the same machinery can also stand up a
**MySQL** instance. That is what makes the MySQL-to-MariaDB migration tutorial
runnable on one laptop: a MySQL source and a MariaDB target, both throwaway.

## Put it to work: rehearse a destructive change

This is the pattern the whole thing exists for.

<div class="prompt" markdown="1">
*I need to add a `NOT NULL` column with a default to a 50-million-row table on
production. Before we do anything: deploy a sandbox on 3311, recreate the table
structure there, fill it with a few million rows, and measure what the `ALTER`
actually does — which algorithm it picks, whether it locks, and how long it
takes. Then tell me whether it is safe to run online.*
</div>

The agent will reach for the `mariadb-alter-table` skill, which is where it
learns about `ALGORITHM=INSTANT`, `ALGORITHM=NOCOPY`, `LOCK=NONE` and
`ALTER ONLINE TABLE` — and it will find out by *running* it rather than by
asserting it. That is a rehearsal you could not easily do by hand, and it costs
one sandbox.

Other jobs in the same shape:

- **Test a version upgrade, or check compatibility across releases.** Two
  sandboxes on two versions and the same script on both — that is
  [Tutorial 10](../compare-server-versions/).
- **Reproduce a bug on a clean server.** No local state, no "works on my
  machine".
- **Try a configuration change**, then measure it rather than argue about it.
- **Review a pull request's migration.** Apply it to a sandbox seeded with the
  current schema, and see what it does.

## Tidy up

<div class="prompt" markdown="1">
*List the sandboxes you have created in this session and delete all of them.*
</div>

Then check the directory yourself — `~/.mariadb-shell/sandboxes/` — because an
orphan from a timed-out run will still be sitting there.

<h2 class="no-step" id="what-you-built">What you learned</h2>

- A sandbox is a folder plus a real server. No Docker, no root, and cleanup is a
  delete.
- A port is all you have to ask for — the password is chosen and registered for
  you. Name one yourself only when something outside the agent has to log in,
  and never ask for a blank one.
- Ask for a version, a location or non-default settings when you actually need
  one.
- The connection is registered for you — there is no setup step between
  deploying a server and using it.
- Ask for the teardown in the same instruction as the creation, "even if a step
  fails".
- The real payoff is rehearsal: dangerous changes get tried somewhere that does
  not matter first.

**Where to go next**

- [Diagnose a slow query](../diagnose-a-slow-query/) — a sandbox is also where
  you test an index without touching production.
- [Migrate from MySQL](../mysql-to-mariadb-migration/) — two sandboxes, one
  MySQL, one MariaDB, one migration.
