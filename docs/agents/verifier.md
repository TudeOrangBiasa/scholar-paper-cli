# Verifier

Solo gate for this repo. Replaces GitHub Actions.

## Command

```bash
bash scripts/verify.sh
```

Prints `verify: all gates passed` and exits 0 when every step passes. Any red step stops the run with a nonzero exit.

## Steps

1. `uv sync --locked`
2. `uv run python -m pytest -q`
3. `uv run ruff check src tests`
4. `uv run ty check src tests`
5. `uv run ruff format --check src tests`
6. `trivy fs` HIGH/CRITICAL (skipped with a note when trivy is not installed)
7. CLI smoke: `skills/verify-spm/scripts/smoke.sh` (offline, isolated cache; skip with `VERIFY_SKIP_SMOKE=1`)

Hook install: `git config core.hooksPath .githooks` is not used; run `scripts/ensure-worktree-hooks` once per clone/worktree (copies `.githooks/pre-push` into the git hooks dir).

## Who runs it

- **pre-push hook** on every push. New worktrees: `scripts/ensure-worktree-hooks --worktree <path>`, then `--check`.
- **the agent**, again, right before `gh pr create`. Paste the real output in the PR body.
- App-driving proof beyond the gate: `skills/verify-spm/`.

Never `git push --no-verify`. Merges trust this gate; no GitHub status check is required.
