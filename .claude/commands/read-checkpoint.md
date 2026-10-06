---
description: Reads a compressed summary of the last session so this session can resume. Usage: /read-checkpoint
---

# Read Checkpoint Command

Where a context file `.claude/PROJECT_CONTEXT.md` already exists, read this file to be able to resume the last session.

## A. `.claude/context/` exists — split layout

`.claude/PROJECT_CONTEXT.md` is the index: the description, the top-level layout table, a table of the context files with what is in each, and whatever cross-cutting sections it carries.

1. Read the index first. It tells you which context file covers which area.
2. Read only the context files this session's work touched — that is the point of the split, so do not read the whole set to write a checkpoint.

## B. `.claude/PROJECT_CONTEXT.md` exists, with no `context/` — single file

Read it, it has the full session information.

## C. Neither exists — new project

Error out stating that `.claude/PROJECT_CONTEXT.md` does not exist and the user needs to run the `/checkpoint` command first.
