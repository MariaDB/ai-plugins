---
name: mariadb-laravel-ai-sdk
description: "Use MariaDB Vector as the store behind Laravel's AI SDK (laravel/ai): generating embeddings, persisting them in a MariaDB vector column, semantic search and giving an agent a similarity-search tool. Use when building RAG, semantic search or agent memory on MariaDB in a Laravel application."
---

# Laravel AI SDK on MariaDB

The `laravel/ai` package generates the embeddings; MariaDB stores and searches them.
Nothing connects the two beyond what the framework already does — see
`mariadb-laravel-vector` for the column, the index and the cast. Requires MariaDB 11.7+
(11.8 LTS recommended) on the `mariadb` driver.

```shell
composer require laravel/ai
php artisan vendor:publish --provider="Laravel\Ai\AiServiceProvider"
php artisan migrate
```

## Generating embeddings

```php
use Illuminate\Support\Str;
use Laravel\Ai\Embeddings;

// One string...
$embedding = Str::of('Napa Valley has great wine.')->toEmbeddings();

// Many at once, with an explicit provider and dimensions...
$response = Embeddings::for(['Napa Valley has great wine.', 'Laravel is a PHP framework.'])
    ->dimensions(1536)
    ->generate(Lab::OpenAI, 'text-embedding-3-small');

$response->embeddings; // [[0.12, 0.45, ...], [0.78, 0.01, ...]]
```

**The dimension count is a contract with the schema.** `vector('embedding', 1536)` accepts
vectors of exactly that length; MariaDB rejects any other length at insert time. Pick the
model first, then size the column.

## Storing them

```php
Document::create([
    'title' => $title,
    'content' => $content,
    'embedding' => Str::of($content)->toEmbeddings(),
]);
```

With `'embedding' => AsVector::class` in the model's casts, the array is written as
`vec_fromtext('[...]')` and read back as an array of floats. Nothing else is needed.

## Searching

```php
$documents = Document::query()
    ->whereVectorSimilarTo('embedding', 'best wineries in Napa Valley')
    ->limit(10)
    ->get();
```

Passing a string rather than a vector is what ties the two halves together: the query
builder calls `Str::of($query)->toEmbeddings(cache: true)` — a macro that only exists once
`laravel/ai` is installed and a provider is configured. Without the package, pass an array
of floats.

Cache the query embedding (`cache: true` is the default on that path): the same question
asked twice should not be billed twice.

## Giving an agent the search as a tool

```php
use App\Models\Document;
use Laravel\Ai\Tools\SimilaritySearch;

public function tools(): iterable
{
    return [
        SimilaritySearch::usingModel(
            model: Document::class,
            column: 'embedding',
            minSimilarity: 0.7,
            limit: 10,
            query: fn ($query) => $query->where('published', true),
        )->withDescription('Search the knowledge base for relevant articles.'),
    ];
}
```

This runs `whereVectorSimilarTo` against MariaDB on every tool call — the constraints of
`mariadb-laravel-vector` all apply, in particular that the vector index is only used when
the query's distance function matches the index's `DISTANCE`.

For a closure-based tool scoped to the current user, the same rule holds:

```php
new SimilaritySearch(using: fn (string $query) => Document::query()
    ->where('user_id', $this->user->id)
    ->whereVectorSimilarTo('embedding', $query)
    ->limit(10)
    ->get());
```

## Reranking

`Laravel\Ai\Reranking` reorders an already-retrieved list. The usual shape is a wide vector
search on MariaDB (cheap, the index does the work) followed by a rerank of the top 50 — not
a rerank of the whole table.

## Pitfalls

- **`Laravel\Ai\Stores` is not MariaDB.** Vector stores in the AI SDK are collections of
  files hosted *by the AI provider*; they are not a driver layer over your database, and no
  configuration points them at MariaDB. To keep the data in MariaDB, use a vector column and
  the query builder as above. Mixing both means two copies of the corpus.
- **Changing embedding model means re-embedding everything.** Distances between vectors
  from different models are meaningless. Store the model name next to the vector, and if the
  new model has a different dimension count the column has to be altered too.
- **`minSimilarity` is a cosine notion.** It becomes `vec_distance_cosine(...) <= 1 - s`.
  A value tuned for one embedding model does not transfer to another.
- **Do not call `Schema::ensureVectorExtensionExists()`** — it throws on MariaDB. See
  `mariadb-laravel-vector`.
- **Embedding generation is a network call.** Generating embeddings inside a request that
  also writes to the database holds a transaction open for the duration; queue the
  ingestion instead.

## Related skills

- `mariadb-laravel-vector` — the column, the index, the cast, the query methods.
- `mariadb-laravel-connector` — driver and version setup.
