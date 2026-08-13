# Domain Context — scholar-paper-cli

spm: CLI for Semantic Scholar. 15 commands, persistent SQLite cache, offline fallback, multilingual semantic search.

## Glossary

- **Paper** — a scholarly publication as represented by Semantic Scholar (paper_id, title, abstract, authors, citations, references).
- **Author** — a scholar. Subject to **author consolidation**.
- **Author consolidation** — merging duplicate author records into one canonical Author: aliases merge (deduplicated), the duplicate's papers re-parent to the canonical author, the duplicate record is deleted. Atomic: either all duplicates merge or none. Missing duplicate ids are skipped and reported, never fatal.
- **Session** — a named working set of papers the user maintains locally.
- **Cache** — persistent SQLite storage of Semantic Scholar responses (`api_cache`) with TTL-based freshness; serves as the offline fallback.
- **Offline mode** — operation when the Semantic Scholar API is unreachable; probe + grace period govern when the CLI stops attempting the network.
- **Embedding** — multilingual-e5-small vector of a paper's abstract, stored for local semantic search (related papers).
- **Materialization** — ensuring a paper exists locally: db lookup → API fetch → parse → persist (and optionally embed). One operation, one module (see `ensure_paper`).
- **Provenance** — where a response came from (`cache`, `api`, `offline_cache`, `embeddings`, or local `db`); reported honestly in every envelope.

## Decisions

Recorded in `docs/adr/` when they crystallize; nothing archived yet.
