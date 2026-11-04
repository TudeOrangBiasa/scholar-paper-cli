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

Test stats: 280 pass; 9 embedding integration tests skip when the model is not downloaded (see `models/README.md`).

See `docs/PLAN.md` for the full plan, `docs/CONFIGURATION.md` for env vars, `docs/WORKFLOW.md` for document-writing integration.

## Agent skills

### Issue tracker

Issues and specs for this repo live as GitHub issues, operated via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Verification gate (solo, local verifier)

No GitHub Actions. The gate is `bash scripts/verify.sh` ([docs/agents/verifier.md](docs/agents/verifier.md), mode in [docs/agents/repo-mode.md](docs/agents/repo-mode.md)). The pre-push hook runs it on every push; run it again before `gh pr create` and paste the real output in the PR body. Never `git push --no-verify`. New worktrees: `scripts/ensure-worktree-hooks --worktree <path>`. Merge once the verifier passed at the PR head; do not wait on GitHub checks. App-driving proof: `skills/verify-spm/`.
