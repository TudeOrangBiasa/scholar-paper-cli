# Install

One-step install for `spm` (scholar-paper-cli). Suitable for AI agents.

## Requirements

- Python 3.13
- uv 0.10+
- git
- Embedding model (~135MB) downloaded separately, see `models/README.md` (only needed for `spm paper --embed` and `spm related`)

## Install

```bash
# Clone (auto-fetches model via git LFS)
git clone https://github.com/TudeOrangBiasa/scholar-paper-cli
cd scholar-paper-cli

# Install Python deps
uv sync

# Verify
uv run pytest -q          # all tests pass
uv run spm --version      # spm 0.1.0
```

## Run

```bash
uv run spm --help
uv run spm search "quantum entanglement" --limit 2
```

Every command prints JSON to stdout and exits 0. Errors print a JSON error envelope and exit non-zero.

## Install the skills

Install the bundled skills (`spm` + `writing-for-agents`) with the Vercel skills CLI:

```bash
npx skills add https://github.com/TudeOrangBiasa/scholar-paper-cli -s spm -s writing-for-agents -g --copy
```

## Environment variables

Optional, set before `uv run spm`:

```bash
# Higher Semantic Scholar rate limits (free key at https://www.semanticscholar.org/product/api)
export SPM_API_KEY=your-key

# Skip API calls entirely (cache-only mode)
export SPM_OFFLINE_MODE=true
```

All env vars: see `docs/CONFIGURATION.md`.

## Verify CLI works

After install, in a terminal:

```bash
uv run spm search "quantum entanglement" --limit 1
```

Expect JSON output: `{"data": {"query": ..., "total": ...}, "meta": {"source": "api"}}`. Run the same command again and `meta.source` becomes `"cache"`.

## Project layout (key paths)

| Path | Purpose |
|------|---------|
| `models/model_quantized.onnx` | mE5-small int8 ONNX, 113MB, git LFS |
| `models/tokenizer.json` | XLM-RoBERTa tokenizer, 16MB |
| `~/.local/share/scholar-paper-cli/cache.db` | SQLite cache (created at runtime) |
| `skills/spm/SKILL.md` | spm CLI skill (commands, output contract, caching) |
| `skills/writing-for-agents/SKILL.md` | Agent-facing docs reference skill |
| `docs/CONFIGURATION.md` | All `SPM_*` env vars |
| `docs/WORKFLOW.md` | Document-writing integration |
| `AGENTS.md` | Project conventions (TDD, ponytail, anti-AI-slop) |

## Common issues

**`git-lfs: command not found` during clone**

Not needed. The model is no longer bundled via git LFS; it is downloaded separately (see `models/README.md`).

**`RuntimeError: Required inputs (['token_type_ids']) are missing`**

Outdated code. Pull latest:
```bash
git pull
```

The model requires `token_type_ids` input. Fixed in the `fix(embeddings)` commit.

**`EmbeddingModelNotFoundError: model not found`**

Model files missing or wrong path. The model is not bundled with the repo; download once:
```bash
# See models/README.md for the exact commands
uvx huggingface-cli download intfloat/multilingual-e5-small onnx/model_quantized.onnx --local-dir models/ --local-dir-use-symlinks False
mv models/onnx/model_quantized.onnx models/ && rmdir models/onnx
```

**Embedding tests show skipped (model not downloaded)**

Expected. The 11 embedding integration tests in `tests/test_embeddings.py` skip when `models/` has no model. Run the download above to enable them.

**`SS API rate limited (429)`**

Without `SPM_API_KEY`: ~100 requests per 5 minutes shared pool. Set key for higher limits.

## Uninstall

```bash
# Remove clone
rm -rf /path/to/scholar-paper-cli

# Remove cache
rm -rf ~/.local/share/scholar-paper-cli

# Remove the skills
npx skills remove spm writing-for-agents
```

## Tests

```bash
uv run python -m pytest -q # all tests
uv run pytest tests/test_docs.py # doc consistency only
uv run ruff check src tests     # lint
uv run ty check src tests       # type check
uv run ruff format --check src tests  # format
```

All four must pass before committing.
