# Session

## Sub-features

add, list, remove; BibTeX export reads the same session.

## How to get to it (user POV)

`spm session list <id>`, `spm session add <id> <paperId>`, `spm session remove <id> <paperId>`.

## Driving it with the CLI

Isolated env from SKILL.md, then `uv run spm session list smoke`. Parse stdout as JSON; `data` is `[]` on an empty cache and `meta.source` is `db`.

## Gotchas

`add` with a paper not in cache needs the API; offline mode makes it fail fast. Seed the cache first when proving `add`.
