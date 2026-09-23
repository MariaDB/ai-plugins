---
order: 6
slug: versioned-schema-with-msm
title: "Version a schema with MSM: create, release, deploy"
description: >-
  Turn the Notes App from a one-off create script into a versioned MariaDB
  Schema Management project — a schema you can ship version 2 of, to servers
  that are still running version 1.
level: intermediate
duration: "60 min"
area: schema-management
tools: ["msm.create_project", "msm.get_sql_content_from_section", "msm.set_section_sql_content", "msm.prepare_release", "msm.generate_deployment_script", "msm.deploy_schema"]
skills: ["mariadb-schema-management", "mariadb-schema-management-create", "mariadb-schema-management-release", "mariadb-schema-management-deploy"]
path_label: "Schema Lifecycle, Step 2"
prerequisites:
  - "[Tutorial 1](../notes-app-sandbox/) — you should have seen a plain create script first, to appreciate what this adds."
  - "The working directory on the MCP server's allowed-paths list. Every `msm.*` tool is path-gated."
---

A create script builds a schema once. The second time you need it, the schema is
already there and half-changed, and the script is useless. **MariaDB Schema
Management (MSM)** is the answer: a project on disk that tracks every version of
a schema, and generates a deployment script that either creates the schema fresh
*or* upgrades whatever older version it finds.

Prefer MSM over a one-off script whenever a schema will evolve and be deployed
somewhere that may hold an earlier version. This tutorial takes the Notes App
through its first release. [Tutorial 7](../ship-a-schema-upgrade/) ships the
second.

## Understand the shape before you start

Two ideas carry the whole system, and the `mariadb-schema-management` skill
teaches the agent both.

**A project directory**, scaffolded for you:

```text
notes_app.msm.project/
├── msm.project.json        # schemaName, license, copyrightHolder, dependencies
├── development/
│   ├── notes_app_next.sql  # the working script — no version in the name
│   └── sections/           # optional SOURCE breakout files
└── releases/
    ├── versions/    notes_app_1.0.0.sql                # full snapshot per release
    ├── updates/     notes_app_1.0.0_to_1.1.0.sql       # migration — you fill this
    └── deployment/  notes_app_deployment_1.0.0.sql     # generated; never edit
```

**A section model.** MSM scripts are plain SQL split by
`-- ##### … MSM Section NNN: Title` banners, and **which section a statement
lives in decides how the deployment script treats it**:

| Section | Contents |
| --- | --- |
| 110 / 120 | `CREATE SCHEMA`, version indicator (provided) |
| 130 | Helper routines used during creation — names must start `msm_` |
| **140** | **Non-idempotent: `CREATE TABLE` and base-data `INSERT`s** |
| **150** | **Idempotent: views, procedures, functions, triggers, events** |
| 170 | Authorization: `CREATE ROLE`, `GRANT` |
| 180 | Optional MariaDB REST Service endpoints |
| 190 | Removal of the `msm_` helpers |
| 910 / 920 | Final version, server-variable restore (provided) |

The split is **idempotent versus not**. Tables and data are state that cannot be
re-run, so they are version-guarded. Everything else is written with
`CREATE OR REPLACE` / `DROP … IF EXISTS` and can safely run every time.

<div class="callout callout--warn" markdown="1">
**Never edit the section banners by hand.** The agent reads and writes sections
through tools that address them by number; a banner edited in your editor
corrupts the file in a way that only shows up at release time. Say which section
you want something in and let the agent put it there.
</div>

## Scaffold the project

<div class="prompt" markdown="1">
*Use the MariaDB Schema Management tools to manage a note-taking app as a
versioned schema project. Create an MSM schema project for a schema named
`notes_app` in the current directory.*
</div>

The scaffolding is a tool call the agent makes; this is what goes past in the
transcript:

```text
msm.create_project(schema_name="notes_app", target_path="/abs/path")
```

<div class="callout" markdown="1">
**Mention a licence by name only if the shell already knows it.** An
unrecognized name is rejected outright rather than guessed at, so *"licence it
GPLv2"* fails. Say nothing and you get no licence header, or paste the licence
text you want.
</div>

## Author version 1.0.0 into the right sections

This is where the section model earns its keep. Tables go in **140**, the view
goes in **150**:

<div class="prompt" markdown="1">
*For the initial version 1.0.0, author two tables — `user` and `note` — plus a
view named `user_activity` that lists users ordered by how many notes they have.
Put the tables in the non-idempotent create section and the view in the
idempotent create section.*
</div>

Naming the sections in the prompt is what keeps the tables and the view apart.
"Non-idempotent create section" and "idempotent create section" are enough — you
do not have to remember that they are numbered 140 and 150, though saying the
numbers works too.

<div class="callout callout--warn" markdown="1">
**The delimiter rule, and why it exists.** In the generated deployment script,
sections **140, 240, 170 and 270** become the *body of a stored procedure*. Write
them as plain `;`-terminated statements with **no `DELIMITER`**, and use dynamic
SQL for conditional DDL. Sections **130, 150, 230, 250, 190 and 290** are emitted
at top level and use `DELIMITER %%` for routine bodies.

Getting this backwards produces a deployment script that fails to parse, with an
error that points at a line you did not write.
</div>

Check what landed where before moving on:

<div class="prompt" markdown="1">
*Read back sections 140 and 150 and show me exactly what is in each.*
</div>

## Prepare the 1.0.0 release

<div class="prompt" markdown="1">
*Prepare the 1.0.0 release and generate its deployment script.*
</div>

Preparing a release snapshots `development/notes_app_next.sql` into
`releases/versions/notes_app_1.0.0.sql` and bumps the development version. For a
first release there is no previous version to migrate from, so no update script
is needed — which is exactly what makes the *second* release the interesting one.
Generating then composes `releases/deployment/notes_app_deployment_1.0.0.sql`.

**That deployment script is the artifact you ship.** It is a create-or-upgrade
script: given an empty server it creates the schema, given an older version it
migrates. It is generated, so never edit it — change the source and regenerate.

## Deploy onto a live server

Deploying needs a server to deploy onto, so ask for a sandbox in the same breath
if you do not have a target:

<div class="prompt" markdown="1">
*Spin up a sandbox on port 3310, connect to it, and deploy version 1.0.0 of the
schema.*
</div>

Against anything whose contents you would miss, ask for a backup first — *"take
a backup into `./backups` before you deploy"* — and the deployment takes one on
the way past. On an empty sandbox it does not matter; make it a habit anyway,
because the prompt you reuse on a real server is the one you wrote here.

## Verify on the server, not in the transcript

<div class="prompt" markdown="1">
*Go and look at the server: which tables and views does `notes_app` actually
have now, and what does `msm_schema_version` say?*
</div>

That last question is the point of the whole exercise: the schema now carries its
own version number, in a `msm_schema_version` view defined by section 910. A
future deployment script reads it to decide whether to create or to upgrade, and
from which version.

## Check the project state

Months later, the thing you will not remember is what was *released* versus what
was merely developed, and which deployment scripts exist for it. Ask:

<div class="prompt" markdown="1">
*Give me the state of this MSM project: which versions have been released, which
deployment scripts exist, and what is the development version sitting at?*
</div>

<h2 class="no-step" id="what-you-built">What you built</h2>

A versioned schema project with one release, a generated deployment script, and
a live server carrying a version number it can be upgraded from.

The distinction to hold onto: **the development script is where you work, the
release is a snapshot, the deployment script is the artifact.** You edit the
first, `prepare_release` makes the second, `generate_deployment_script` makes the
third, and you edit the third never.

**Where to go next**

- [Ship a schema upgrade](../ship-a-schema-upgrade/) — version 1.1.0, and the one
  rule everyone gets wrong the first time.
