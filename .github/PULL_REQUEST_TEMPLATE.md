## What

The problem being solved and the change in two or three sentences.

## Changes

- List of files and symbols touched
- APIs introduced, changed, or removed

## Verification

```bash
bash scripts/verify.sh   # paste the real output; no GitHub Actions in this repo
```

Smoke observations (CLI changes only): command run, JSON output, exit code.

## Notes

Tradeoffs, follow-ups, anything a reviewer should know.

- [ ] Branch is not `main`, name follows `type/slug`
- [ ] Commit messages follow `type(scope): subject`
- [ ] Tests written first (TDD)
- [ ] `bash scripts/verify.sh` prints `verify: all gates passed` (pre-push runs it; never `--no-verify`)
- [ ] Changelog entry added under `Unreleased`
- [ ] Agent docs updated for behavior changes (`AGENTS.md` or `skills/`)
- [ ] No heavy imports at module top level
- [ ] stdout stays JSON-only (CLI changes only)
