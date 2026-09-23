---
name: mariadb-laravel-vector
description: "MariaDB Vector in a Laravel (PHP) application: vector columns, VECTOR INDEX, the AsVector Eloquent cast and similarity search with the query builder. Use when building semantic search, RAG or embedding storage on MariaDB with Laravel or Eloquent."
---

# MariaDB Vector with Laravel

Requires **MariaDB 11.7+** (11.8 LTS recommended) and **Laravel 13**, on the `mariadb`
driver — see `mariadb-laravel-connector`. Vector support is native to the framework:
no Composer package is needed to store or query vectors.

## Migration

```php
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

Schema::create('documents', function (Blueprint $table) {
    $table->id();
    $table->string('title');
    $table->text('content');
    $table->vector('embedding', 1536);
    $table->timestamps();

    $table->vectorIndex('embedding');
});
```

`vector('embedding', 1536)` emits `vector(1536) not null`. `vectorIndex('embedding')`
emits:

```sql
alter table `documents` add vector index `documents_embedding_vectorindex` (`embedding`) M=6 DISTANCE=cosine
```

`$table->vector('embedding', 1536)->index()` is equivalent — on a vector column, the
fluent `index()` is routed to `vectorIndex()`.

To drop it, pass the index name, not the column:

```php
$table->dropVectorIndex('documents_embedding_vectorindex');
```

### Never call `Schema::ensureVectorExtensionExists()` on MariaDB

That helper exists for PostgreSQL's `pgvector` extension and throws on any other
connection:

```
RuntimeException: Extensions are only supported by Postgres.
```

MariaDB needs no extension — `VECTOR` is a built-in column type. Migrations that must run
on both engines should guard it:

```php
if (DB::connection() instanceof Illuminate\Database\PostgresConnection) {
    Schema::ensureVectorExtensionExists();
}
```

### Index constraints to respect

- The indexed column must be `NOT NULL`. Laravel's `vector()` is `NOT NULL` by default —
  do not add `->nullable()` on a column you intend to index.
- **One vector index per table.** Two indexed vector columns on the same table are rejected
  by the server.
- `M` (graph degree, 3–200, default 6) and `DISTANCE` (`cosine` or `euclidean`) are fixed at
  creation time. Changing them means dropping and recreating the index.
- The index is only used when the query's distance function matches the index's `DISTANCE`.
  An index created with `DISTANCE=cosine` does nothing for a `VEC_DISTANCE_EUCLIDEAN` query —
  the server falls back to a full scan and still returns correct rows, just slowly.

## Eloquent cast

```php
use Illuminate\Database\Eloquent\Casts\AsVector;

class Document extends Model
{
    protected function casts(): array
    {
        return ['embedding' => AsVector::class];
    }
}
```

Assign a plain PHP array of floats; the cast writes `vec_fromtext('[...]')` and reads back
MariaDB's little-endian float32 bytes as an array of floats. Never write the raw binary or a
JSON string to the column yourself.

```php
Document::create([
    'title' => 'Napa Valley',
    'content' => $content,
    'embedding' => $embedding,   // array<int, float>, exactly as many values as the column's dimensions
]);
```

A dimension mismatch is rejected by the server at insert time.

## Querying

```php
$documents = Document::query()
    ->whereVectorSimilarTo('embedding', $queryEmbedding, minSimilarity: 0.6)
    ->limit(10)
    ->get();
```

`whereVectorSimilarTo` filters on **cosine similarity** (`0.0`–`1.0`, `1.0` identical) and
orders by similarity. It is a wrapper: similarity `s` becomes `vec_distance_cosine(...) <= 1 - s`.

Lower-level methods, when the threshold and the ordering must be controlled separately:

```php
Document::query()
    ->select('*')
    ->selectVectorDistance('embedding', $queryEmbedding, as: 'distance')
    ->whereVectorDistanceLessThan('embedding', $queryEmbedding, maxDistance: 0.3)
    ->orderByVectorDistance('embedding', $queryEmbedding)
    ->limit(10)
    ->get();
```

All four compile to `vec_distance_cosine(<column>, vec_fromtext(?))` on MariaDB.

### Passing a string instead of a vector

Every one of these methods also accepts a plain string, which is embedded on the fly:

```php
Document::query()
    ->whereVectorSimilarTo('embedding', 'best wineries in Napa Valley')
    ->limit(10)
    ->get();
```

This calls `Str::of($query)->toEmbeddings(cache: true)`, a macro provided by the
**`laravel/ai`** package. Without that package installed and an embeddings provider
configured, pass an array of floats instead.

## Pitfalls

- **Cosine only in the framework.** `compileVectorDistanceExpression()` always emits
  `vec_distance_cosine`. For `VEC_DISTANCE_EUCLIDEAN`, use `whereRaw()`/`selectRaw()` with a
  matching `DISTANCE=euclidean` index, or a community package that adds the metric
  (e.g. `rhaima96/laravel-vector-metrics`).
- **Normalize consistently.** Cosine distance ignores magnitude, but mixing embeddings from
  different models or versions in one column makes distances meaningless. Store the model
  name alongside the vector and re-embed the whole table when it changes.
- **`M=6` is the framework default**, not a tuned value. For large tables, create the index
  with a higher `M` (more accuracy, more memory) using a raw statement.
- **Check the index is actually used** before blaming the server:

```sql
EXPLAIN SELECT id FROM documents
ORDER BY VEC_DISTANCE_COSINE(embedding, VEC_FROMTEXT('[...]')) LIMIT 10;
```

A `LIMIT` and an `ORDER BY` on the matching distance function are what let the optimizer pick
the vector index.

## Related skills

- `mariadb-laravel-connector` — driver and version setup.
- `mariadb-vector` / `mariadb-vector-functions` — the server-side reference.
