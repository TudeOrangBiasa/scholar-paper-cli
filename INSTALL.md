# Install

One-step install for `spm` (scholar-paper-cli). Suitable for AI agents.

## Requirements

- Python 3.13
- uv 0.10+
- git (with git-lfs 3.0+)
- ~150MB disk (model bundled via git LFS)

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

## Install the skill

Teach your agent the CLI via the bundled skill:

```bash
./skills.sh                     # installs into ~/.agents/skills
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
| `skills/spm/SKILL.md` | Agent skill teaching the CLI |
| `docs/CONFIGURATION.md` | All `SPM_*` env vars |
| `docs/WORKFLOW.md` | Document-writing integration |
| `AGENTS.md` | Project conventions (TDD, ponytail, anti-AI-slop) |

## Common issues

**`git-lfs: command not found` during clone**

The model file is a 113MB regular git object without LFS. Install git-lfs:
```bash
# Ubuntu/Debian
sudo apt install git-lfs && git lfs install

# macOS
brew install git-lfs && git lfs install

# Then re-clone
```

**`RuntimeError: Required inputs (['token_type_ids']) are missing`**

Outdated code. Pull latest:
```bash
git pull
```

The model requires `token_type_ids` input. Fixed in `6e209ed`.

**`EmbeddingModelNotFoundError: model not found`**

Model files missing or wrong path. Check:
```bash
ls -la models/
# Should show: model_quantized.onnx (~113MB) + tokenizer.json (~16MB)
```

If files are 0 bytes or pointers, run `git lfs pull`.

**Tests show skipped (model not downloaded)**

Same as above. LFS not pulled. Run `git lfs pull`.

**`SS API rate limited (429)`**

Without `SPM_API_KEY`: ~100 requests per 5 minutes shared pool. Set key for higher limits.

## Uninstall

```bash
# Remove clone
rm -rf /path/to/scholar-paper-cli

# Remove cache
rm -rf ~/.local/share/scholar-paper-cli

# Remove the skill
rm -rf ~/.agents/skills/spm
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
