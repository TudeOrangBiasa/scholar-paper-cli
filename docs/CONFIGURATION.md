# Configuration

All config via `SPM_*` environment variables. Set in shell or `.env`.

## Semantic Scholar API

### `SPM_API_KEY`

Optional. Semantic Scholar API key for higher rate limits.

Get one (free) at https://www.semanticscholar.org/product/api

```bash
export SPM_API_KEY=your-key-here
```

Without a key, you are in the shared pool (5k requests per 5 min total).

### `SPM_SS_API_BASE`

- Type: URL
- Default: `https://api.semanticscholar.org/graph/v1`

Override for testing or proxies.

## Cache

### `SPM_CACHE_PATH`

- Type: file path
- Default: `~/.local/share/scholar-paper-cli/cache.db`

XDG-compatible default. The `~` tilde expands to the home directory.

### `SPM_CACHE_TTL_DAYS`

- Type: integer
- Default: 30
- Valid: 1 or greater

Papers are immutable. 30 day TTL is conservative.

## Offline mode

### `SPM_OFFLINE_MODE`

- Type: boolean
- Default: `false`

Set to `true` to skip all API calls. Only cached data is returned.

### `SPM_OFFLINE_PROBE_TIMEOUT_SECONDS`

- Type: float
- Default: 2.0
- Valid: 0.5 to 10.0

How long to wait before deciding the API is unreachable.

### `SPM_OFFLINE_PROBE_GRACE_SECONDS`

- Type: integer
- Default: 60
- Valid: 1 to 600

Grace period before retrying the API after it went offline.

## Embedding model

### `SPM_EMBEDDING_MODEL`

- Type: string
- Default: `intfloat/multilingual-e5-small`
- Valid: `intfloat/multilingual-e5-small` or `none`

Set to `none` to disable embeddings. Disables `spm related` KNN search.

## Default limits

### `SPM_DEFAULT_SEARCH_LIMIT`

- Type: integer
- Default: 10
- Valid: 1 to 100

Default result limit for search commands.

### `SPM_DEFAULT_PAPERS_LIMIT`

- Type: integer
- Default: 20
- Valid: 1 to 100

Default paper count for detail commands.

### `SPM_DEFAULT_CITATIONS_LIMIT`

- Type: integer
- Default: 100
- Valid: 1 to 1000

Default limit for citation/reference commands.
