# Contributing

Thanks for contributing to scholar-paper-cli. Read this before you start. It covers the rules for working on this project, the coding standards, and the pull request format.

## Rules for working on this project

1. **Never work on `main` directly.** Create a branch:
   - `feat/<slug>` for new features (example: `feat/embed-flag`)
   - `fix/<slug>` for bug fixes (example: `fix/offline-probe`)
   - `docs/<slug>` for documentation (example: `docs/install-rewrite`)
   - `refactor/<slug>`, `test/<slug>`, `chore/<slug>` for the rest
2. **One concern per branch and per PR.** No drive-by changes. If you touch a file for one reason, do not edit it for another.
3. **Commit messages use the `type(scope): subject` format.** Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`. Examples:
   - `feat(cli): add --embed flag to paper`
   - `fix(cache): honor offline flag on stale reads`
   - `docs(readme): document spm commands`
4. **Write tests first (TDD, red-green-refactor).** Every behavior change ships with tests that fail before the change and pass after. Tests go through public interfaces, never private helpers.
5. **Keep the four gates green before pushing:**
   ```bash
   uv run pytest -q                 # 281 tests, all pass
   uv run ruff check src tests      # lint
   uv run ty check src tests        # type check
   uv run ruff format --check src tests  # format
   ```
6. **Update the changelog.** Add an entry under `Unreleased` in `CHANGELOG.md` using the section keywords: `Added`, `Changed`, `Removed`, `Fixed`, `Tests`. Keep old entries untouched (historical record).
7. **Do not rewrite historical records.** `docs/PLAN.md`, `docs/architecture.drawio*`, and old `CHANGELOG.md` entries document the MCP-era design. Leave them alone.
8. **Read [PHILOSOPHY.md](PHILOSOPHY.md) before making design decisions.** It explains why the CLI, the JSON contract, the lazy imports, and the cache semantics exist. A change that fights the philosophy needs the philosophy updated too, not ignored.
9. **Behavior changes must ship agent docs.** If a command, flag, error type, or cache semantics changes, update `AGENTS.md` or the bundled skills (`skills/spm/SKILL.md`, `skills/writing-for-agents/`) in the same PR. The docs-sync test in `tests/test_docs.py` fails when a bundled skill is missing.

## Coding standards

- **Type hints everywhere.** Annotate every function signature and public attribute. `Any` is a code smell; prefer precise types (`str | None`, generics). The `ty` gate enforces this.
- **TDD + ponytail.** Tests first via public interfaces, minimum code to pass, no premature abstractions. Delete code that is not pulling its weight.
- **uv is the dependency tool; `pyproject.toml` is the source of truth.** Never `pip install` ad hoc. Adding a dependency requires justification in the PR body; prefer stdlib (the CLI is argparse-only by design).
- **Lazy imports are a contract.** The CLI must start fast (~0.2s). Never add `numpy`, `onnxruntime`, `tokenizers`, or other heavy imports at module top level. Put them inside functions that need them (see `storage/embeddings.py`).
- **JSON-only CLI output.** stdout carries exactly one JSON object: `{"data": ..., "meta": ...}` on success, `{"error": {"type", "message"}}` on failure. Exit codes: 0 ok, 1 runtime error, 2 argparse usage. No colors, spinners, or prompts. Diagnostics go to stderr only for internal errors.
- **Prose conventions (applies to all written content in this repo):** caveman prose, no em-dash, no ASCII art. Diagrams use drawio; Mermaid only as a fallback. Academic references use "Author (Year)" citation style.
- **Session and cache semantics are load-bearing.** 30-day TTL, offline fallback with `meta.offline: true`, `SPM_OFFLINE_MODE=true` forces cache-only. Do not change them casually; they are documented in `skills/spm/SKILL.md`.
- **Model bundling.** The embedding model ships via git LFS. Model paths resolve from `Path(SPM_CACHE_PATH).parent/models/`. Embedding commands degrade to an `EmbeddingError` JSON error when the model is missing; that is documented behavior, not a bug.

## Pull request format

Title: `type(scope): short description` (example: `feat(api): add batch search endpoint`).

Body sections, in order:

1. **What** — the problem and the change in two or three sentences.
2. **Changes** — bullet list of files/symbols touched, APIs introduced or removed.
3. **Verification** — exact commands run and their results (test count, gate output, smoke test observations). Do not write "tests pass" without the output.
4. **Notes** — tradeoffs, follow-ups, or anything a reviewer should know.

The template lives at `.github/PULL_REQUEST_TEMPLATE.md` and is filled in automatically when you open a PR.

Checklist before opening:

- [ ] Branch is not `main`, name follows `type/slug`
- [ ] Commit messages follow `type(scope): subject`
- [ ] Tests written first (TDD), covering the changed behavior
- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check src tests` passes
- [ ] `uv run ty check src tests` passes
- [ ] `uv run ruff format --check src tests` passes
- [ ] Changelog entry added under `Unreleased`
- [ ] No heavy imports at module top level
- [ ] stdout stays JSON-only (CLI changes only)
