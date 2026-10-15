---
name: mariadb-schema-create-script
description: "Best practices when writing a MariaDB-specific database script. Use when asked to create or modify a database create script for MariaDB."
---

# MariaDB Database Scripts Best Practices

Assume MariaDB version 11.8 if not explicitly told.

Always create a comment before each database schema object, to describe what it is indented for.

## Start and End Block that should always be added

The SQL script should always start with the following block, to set the correct checks and SQL mode.

```sql
-- Save current session settings and disable checks for faster, safer bulk import
SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0;
SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0;
SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO,STRICT_TRANS_TABLES';
SET @OLD_NOTE_VERBOSITY=@@NOTE_VERBOSITY, NOTE_VERBOSITY=0;

-- Preserve current charset/collation settings, then switch to utf8mb4 for the import
SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT, @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS;
SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION;
SET NAMES utf8mb4;
```

The SQL script should always end with the following block, to restore the previous check state and SQL mode.

```sql
-- Restore original settings
SET SQL_MODE=@OLD_SQL_MODE, FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS;
SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS, NOTE_VERBOSITY=@OLD_NOTE_VERBOSITY;
SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT, CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS;
SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION;
```

## SQL Statement Syntax

## Database or Schema

Always use `SCHEMA` instead of `DATABASE` where applicable.

Always use `CREATE SCHEMA IF NOT EXISTS` rather than `CREATE DATABASE`.

Read the `mariadb-create-database` skill before creating the SQL command.

## Tables

Unless told otherwise, use the MariaDB native UUID datatype for primary key columns for tables that will most likely be exposed directly to client applications. This is done in order to prevent enumeration attacks, hide business intelligence and prevent information leakage about record creation order.

> **Important**: For UUIDs always use the native MariaDB UUID datatype, usage: `UUID NOT NULL DEFAULT UUID_v7()`. Never use `CHAR(36)`.

Always use `CREATE OR REPLACE TABLE` unless told otherwise.

Read the `mariadb-create-table` skill before creating the first CREATE TABLE SQL command.

### Table Data

Always place the `INSERT` statements for all tables after the creation of the schema objects.

## Indexes

Read the `mariadb-create-index` skill before creating the first CREATE INDEX SQL command.

## Views

Read the `mariadb-create-view` skill before creating the first CREATE VIEW SQL command.
