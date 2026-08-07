-- v2: generic cache for API responses (decouples cache from papers/authors tables)
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    params_json TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    ttl_until TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_api_cache_endpoint ON api_cache(endpoint);
