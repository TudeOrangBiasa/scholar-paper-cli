## What

The problem being solved and the change in two or three sentences.

## Changes

- List of files and symbols touched
- APIs introduced, changed, or removed

## Verification

```bash
# exact commands run and their output
uv run pytest -q
uv run ruff check src tests
uv run ty check src tests
uv run ruff format --check src tests
```

Smoke observations (CLI changes only): command run, JSON output, exit code.

## Notes

Tradeoffs, follow-ups, anything a reviewer should know.

- [ ] Branch is not `main`, name follows `type/slug`
- [ ] Commit messages follow `type(scope): subject`
- [ ] Tests written first (TDD)
- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check src tests` passes
- [ ] `uv run ty check src tests` passes
- [ ] `uv run ruff format --check src tests` passes
- [ ] Changelog entry added under `Unreleased`
- [ ] Agent docs updated for behavior changes (`AGENTS.md` or `skills/`)
- [ ] No heavy imports at module top level
- [ ] stdout stays JSON-only (CLI changes only)
