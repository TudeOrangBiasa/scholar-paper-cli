---
name: spm
description: Use when you need to search academic papers or authors, fetch paper details, citations, references, recommendations or related papers, track a working session, or export BibTeX — via the `spm` CLI (Semantic Scholar with persistent SQLite cache, offline fallback, multilingual search, JSON output).
---

# spm

`spm` is a JSON-only CLI for Semantic Scholar. 15 commands, persistent SQLite cache (30-day TTL), offline fallback, multilingual semantic search. Every command prints one JSON object to stdout and exits 0 on success.

## Install

```bash
git clone https://github.com/TudeOrangBiasa/scholar-paper-cli
cd scholar-paper-cli
uv sync
```

Run via `uv run spm ...` from the repo, or install the published package for a bare `spm`:

```bash
uv tool install scholar-paper-cli
```

Embedding model: looked up at `Path(SPM_CACHE_PATH).parent/models/` (default `~/.local/share/scholar-paper-cli/models/`, bundled via git LFS). If the model files are missing, `spm paper <id> --embed` and `spm related <id>` fail with a JSON `EmbeddingError` and exit 1. This is documented behavior, not a bug: embedding commands degrade cleanly without the model.

Env vars (all optional):

| Var | Effect |
|-----|--------|
| `SPM_API_KEY` | Semantic Scholar API key (higher rate limits; free at semanticscholar.org/product/api) |
| `SPM_OFFLINE_MODE=true` | Force cache-only mode, never call the API |
| `SPM_CACHE_PATH` | SQLite cache path (default `~/.local/share/scholar-paper-cli/cache.db`) |
| `SPM_EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` or `none` to disable embeddings |

## Command reference

| Command | Args | Flags (default) | Description |
|---------|------|-----------------|-------------|
| `spm search` | `<query>` | `--limit` (10), `--offset` (0) | Search papers by query |
| `spm paper` | `<paper_id>` | `--embed` | Paper details, persists to cache; `--embed` also stores its embedding |
| `spm citations` | `<paper_id>` | `--limit` (100), `--offset` (0) | Papers that cite this paper |
| `spm references` | `<paper_id>` | `--limit` (100), `--offset` (0) | Papers referenced by this paper |
| `spm author-search` | `<query>` | `--limit` (10), `--offset` (0) | Search authors by name |
| `spm author` | `<author_id>` | — | Author profile, persists to cache |
| `spm author-top` | `<author_id>` | `--limit` (10) | Author's most-cited papers |
| `spm author-duplicates` | `<query>` | `--limit` (50), `--threshold` (0.8) | Group search results by name similarity |
| `spm consolidate` | `<canonical> <dup>...` | — | Merge duplicate authors into the canonical author |
| `spm recommend` | `<paper_id>` | `--limit` (100) | Semantic Scholar recommendations |
| `spm related` | `<paper_id>` | `--k` (10) | Locally computed semantic neighbors (needs embeddings) |
| `spm session add` | `<session> <paper_id>` | — | Add a paper to a session (auto-fetches if not cached) |
| `spm session list` | `<session>` | — | List session papers, oldest first |
| `spm session remove` | `<session> <paper_id>` | — | Remove a paper from a session |
| `spm bibtex` | `<session>` | — | Export session papers as concatenated BibTeX |

## Output contract

Success, one JSON object on stdout, exit 0:

```json
{"data": {...}, "meta": {"source": "cache|api|offline_cache|embeddings", "cached": true, "fetched_at": "...", "ttl_until": "...", "offline": false, "cache_key": "..."}}
```

`data` shape varies by command: search results are `{"query", "total", "offset", "next_offset", "data": [...]}`; lists are JSON arrays; `bibtex` is a string.

Errors, one JSON object on stdout, non-zero exit:

```json
{"error": {"type": "OfflineError", "message": "..."}}
```

Exit codes: 0 ok, 1 runtime error (package error types like `OfflineError`, `APINotFoundError`, `EmbeddingError`, or `InternalError`), 2 argparse usage error. Tracebacks go to stderr only for internal errors; never rely on stderr for normal diagnostics.

## Caching semantics

- Cache TTL is 30 days. Repeat a query and `meta.source` is `"cache"`, no API call.
- When the API is unreachable but stale cache exists, you get the cached data with `meta.offline: true`.
- `SPM_OFFLINE_MODE=true` forces cache-only: repeat queries hit cache; a cache miss raises `OfflineError`.
- Offline fallback is the same behavior the MCP-era server had; nothing else changes.

## Embeddings

- `spm paper <id> --embed` computes the abstract embedding and persists it in SQLite.
- `spm related <id>` embeds the target paper (if needed), then KNN-searches stored vectors.
- A fresh cache has no vectors: `related` returns few or no neighbors until you run `paper --embed` on several papers. Build the corpus first, then query `related`.

## Workflow recipes

Research pipeline:

```bash
spm search "machine learning interpretability" --limit 5
spm paper <paper_id>
spm session add manuscript-v1 <paper_id>     # repeat per interesting paper
spm session list manuscript-v1
spm bibtex manuscript-v1                     # paste into manuscript.tex / proposal.md
```

Related-papers corpus:

```bash
spm paper <seed1> --embed
spm paper <seed2> --embed
spm related <seed1> --k 10                   # now returns real neighbors
spm session add manuscript-v1 <neighbor_id>
```

Multilingual search (Indonesian example; model covers 100+ languages):

```bash
spm search "machine learning interpretabilitas"
```
