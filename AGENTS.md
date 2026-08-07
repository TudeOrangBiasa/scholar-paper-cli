# scholar-paper-cli

spm: CLI for Semantic Scholar. 15 commands, persistent SQLite cache, offline fallback, multilingual semantic search.

Status: complete. 14 of 14 planned issues done, plus 10 review fixes applied. spm CLI live, skills at skills/spm/ and skills/writing-for-agents/ (install via `npx skills add <repo> -g`).

Stack: Python 3.13, argparse, httpx, SQLite + sqlite-vec, ONNX (multilingual-e5-small), pytest + ruff + ty.

Conventions:
- Caveman prose for written content (no em-dash, no ASCII art, drawio for diagrams, Mermaid only as fallback).
- "Author (Year)" citation style for academic refs.
- Type hints everywhere.
- uv for deps, pyproject.toml is source of truth.
- TDD + ponytail: tests first via public interfaces, minimum code, no premature abstractions.

Workflow pattern: TDD (red-green-refactor) + ponytail (full intensity) + database-migrations for DDL.

Skills stack:
- tdd, ponytail, coding-standards (every issue)
- database-migrations (DDL changes)
- humanizer (any prose, auto-loaded)
- impeccable (design direction, anti-AI-slop visual prompts)
- drawio (architecture diagrams)

Test stats: 281 pass; 11 embedding integration tests skip when the model is not downloaded (see `models/README.md`).

See `docs/PLAN.md` for the full plan, `docs/CONFIGURATION.md` for env vars, `docs/WORKFLOW.md` for document-writing integration.
