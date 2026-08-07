# Philosophy

Why scholar-paper-cli is built the way it is. This explains the reasoning behind the design decisions, so future changes fit the intent instead of fighting it.

## A CLI beats an MCP server

The project started as an MCP server. That tied every feature to MCP-capable clients: if your agent or tool cannot speak MCP, the whole thing is dead weight.

A CLI runs anywhere bash runs: any agent, any terminal, cron jobs, shell pipelines. `spm search "x" | jq .data` works everywhere. The cost is losing native MCP tool discovery, and `spm --help` plus the skill file close that gap.

## stdout is data, nothing else

Every command prints exactly one JSON object. Success is `{"data", "meta"}`, failure is `{"error", "type, message"}`, exit codes are 0, 1, or 2. No colors, no spinners, no prompts, no progress bars.

Agents and humans parse the same bytes. The contract is the interface. Adding decoration to stdout would break that contract for everyone.

## Latency is a feature

A CLI tool that takes a second to start feels broken. The target is ~0.2s for non-embedding commands. The embedding stack (onnxruntime, tokenizers, numpy) is heavy and is only needed by two commands, so it loads lazily, inside functions that use it. The import order is a performance contract: do not break it by importing heavy modules at file top.

## Local-first: you own your research

Semantic Scholar is rate-limited, occasionally down, and shared-pool quotas run out. So the cache is the source of truth:

- SQLite with a 30-day TTL. Repeat queries cost zero API calls.
- Offline detector with a grace period. When the API is unreachable, you still get stale-but-cached data, flagged with `meta.offline: true`.
- `SPM_OFFLINE_MODE=true` forces cache-only. Deterministic, scriptable, no network surprises.

Sessions and BibTeX exist for the same reason: your reading list and your bibliography are yours, stored locally, exported in one command.

## Determinism over magic

The API is the only unpredictable part, and it is walled off behind the cache. Everything else is explicit:

- The same command twice gives the same JSON shape.
- Errors carry the exception class name (`OfflineError`, `APINotFoundError`, `EmbeddingError`), so callers can branch on type, not parse prose.
- Internal failures print a traceback on stderr and a JSON `InternalError` on stdout. Diagnostics never pollute the data stream.

## Multilingual by default

Embeddings run locally on `intfloat/multilingual-e5-small` (ONNX, int8, 384-dim). 100+ languages, including Indonesian: `spm search "machine learning interpretabilitas"` finds the same papers as the English query. Local inference means no per-query embedding API cost and no data leaving your machine.

Degradation is documented, not accidental: if the model files are missing, `spm paper --embed` and `spm related` return an `EmbeddingError` JSON error. The tool still works; only the embedding features are off.

## Minimalism as a constraint

- The CLI is argparse from the stdlib. No click, no typer, no dependency for a flag parser.
- Bare-minimum UX: no colors, spinners, or prompts. The CLI serves agents first.
- One command (`spm`), one skill (`skills/spm/SKILL.md`), one package (`scholar_paper_cli`), 15 subcommands that mirror the original tool set so nothing learned before is lost.
- `--embed` is a flag on `spm paper` only. A global flag would be dead code on 14 of 15 commands.

## Engineering practice

- TDD, red-green-refactor, ponytail intensity. Tests first via public interfaces, minimum code to pass.
- No premature abstractions. If a layer stops pulling weight, delete it (the FastMCP server was deleted wholesale, not kept for nostalgia).
- History is a record, not a moving target. `docs/PLAN.md`, the old CHANGELOG entries, and the drawio-era architecture stay as written. New work is described in new sections.

## What this means for contributors

- Do not add dependencies without justification; stdlib first.
- Do not decorate stdout; the JSON contract is the product.
- Do not eager-import heavy modules; measure startup time.
- Do not silently change cache or offline semantics; the skill file documents them as user-visible behavior.
- Do not rewrite history; append to it.

When a change fights one of these, the change is probably wrong. When a change updates one of these because the world moved, write it down in the changelog and this file.
