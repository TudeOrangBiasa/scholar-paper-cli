---
name: verify-spm
description: Drive the scholar-paper-cli `spm` CLI like a user (offline, isolated cache) and capture JSON evidence. Use before opening a PR that touches CLI commands, storage, or output contract.
---

# Verify spm

Primary surface: the `spm` CLI (JSON on stdout). No server, no UI.

## Launch

`uv sync --locked`, then run each command with an isolated cache:

```sh
export SPM_CACHE_PATH="$(mktemp -d)/cache.db" SPM_OFFLINE_MODE=true SPM_EMBEDDING_MODEL=none
uv run spm --help
```

`SPM_OFFLINE_MODE=true` keeps every drive off the Semantic Scholar network; `SPM_CACHE_PATH` keeps the user's `~/.local/share/scholar-paper-cli/cache.db` untouched.

## Doctor

`uv run spm --version` exits 0 and prints a version. If it fails, `uv sync --locked` again.

## Drive

- `uv run spm session list <id>` → `{"data":[],"meta":{"source":"db",...}}` on an empty cache.
- `uv run spm session add <id> <paperId>` / `remove` change what `list` returns.
- Network commands (`search`, `paper`, `citations`) need the API; with offline mode they must answer from cache or return a JSON error, never a traceback.

## Evidence

`skills/verify-spm/scripts/smoke.sh` writes `.scratch/verify/<run>/` (version, JSON responses). Check side effects: the cache db exists at `SPM_CACHE_PATH` after the run.

## Cleanup

The smoke deletes its temp cache dir on exit. Evidence under `.scratch/verify/` stays (gitignored).

## Helpers

- `bash skills/verify-spm/scripts/smoke.sh` (also step "CLI smoke" in `scripts/verify.sh`).
- Feature map: `features/README.md`.
