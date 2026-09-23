---
name: mariadb-laravel-connector
description: "Connect a Laravel (PHP) application to MariaDB: PDO requirements, the dedicated mariadb driver, version support and Docker/Sail setup. Use when setting up, configuring or debugging a MariaDB connection in a Laravel or PHP application."
---

# MariaDB with Laravel

Assume MariaDB 11.8 (LTS) and Laravel 13 if not explicitly told.

Laravel ships a **dedicated MariaDB driver** since Laravel 11. It is not the same as the
`mysql` driver: it has its own connection, connector, query grammar and schema grammar,
and it is the only one that emits MariaDB-specific SQL.

## Requirements

- PHP 8.2+ with the `pdo_mysql` extension (`php -m | grep pdo_mysql`).
- No extra Composer package. MariaDB support is part of the framework.

## Configuration

`.env`:

```dotenv
DB_CONNECTION=mariadb
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=laravel
DB_USERNAME=sail
DB_PASSWORD=password
```

`config/database.php` — the `mariadb` connection is identical to the `mysql` one except
for the `driver` key:

```php
'mariadb' => [
    'driver' => 'mariadb',
    'url' => env('DB_URL'),
    'host' => env('DB_HOST', '127.0.0.1'),
    'port' => env('DB_PORT', '3306'),
    'database' => env('DB_DATABASE', 'laravel'),
    'username' => env('DB_USERNAME', 'root'),
    'password' => env('DB_PASSWORD', ''),
    'charset' => env('DB_CHARSET', 'utf8mb4'),
    'collation' => env('DB_COLLATION', 'utf8mb4_unicode_ci'),
    'prefix' => '',
    'prefix_indexes' => true,
    'strict' => true,
    'engine' => null,
],
```

A fresh Laravel application already contains this block — only `DB_CONNECTION` has to be
changed.

## Always use the `mariadb` driver against a MariaDB server

Pointing the `mysql` driver at a MariaDB server appears to work — basic CRUD and most
migrations run fine — and then fails in specific, hard-to-diagnose places:

| Feature | `mariadb` driver | `mysql` driver on a MariaDB server |
| --- | --- | --- |
| Vector distance queries | supported | `RuntimeException: Vector distance queries are only supported by Postgres and MariaDB.` |
| `uuid()` column | native `uuid` type (MariaDB 10.7+) | `char(36)` |
| `renameColumn()` | legacy syntax before 10.5.2 | MySQL syntax, fails on old servers |
| `geometry()` SRID | `ref_system_id=` | `srid=`, rejected by MariaDB |
| `date()` / `year()` defaults | `CURRENT_TIMESTAMP` handled | wrong default emitted |
| Lateral joins | explicit "not supported" error | invalid SQL sent to the server |

Check what a connection actually uses:

```php
DB::connection()->getDriverName();          // "mariadb"
DB::connection()->getServerVersion();       // "11.8.2-MariaDB"
DB::connection()->isMaria();                // true
```

## Version support

- Laravel's own CI runs the integration suite against MariaDB **10.11, 11.8 LTS and 12.3 LTS**.
- **Vector columns and vector distance queries require MariaDB 11.7+** (11.8 LTS recommended;
  `VECTOR` was a preview in 11.7 and became GA in 11.8).
- A multi-table `DELETE ... ORDER BY ... LIMIT` is accepted from **11.8.1** (MDEV-30469);
  it raises an error on earlier versions and on MySQL. Gate any code that relies on it on the
  server version rather than on the driver name.

## Docker / Laravel Sail

```yaml
services:
  mariadb:
    image: 'mariadb:11.8'
    environment:
      MARIADB_ROOT_PASSWORD: '${DB_PASSWORD}'
      MARIADB_DATABASE: '${DB_DATABASE}'
      MARIADB_USER: '${DB_USERNAME}'
      MARIADB_PASSWORD: '${DB_PASSWORD}'
    ports:
      - '${FORWARD_DB_PORT:-3306}:3306'
    volumes:
      - 'sail-mariadb:/var/lib/mysql'
    healthcheck:
      test: ['CMD', 'healthcheck.sh', '--connect', '--innodb_initialized']
```

`sail up` then `php artisan migrate`. Use `mariadb:11.8` or later — the `mariadb:10` image
cannot run vector workloads.

## Related skills

- `mariadb-laravel-vector` — vector columns, indexes and similarity search in Laravel.
