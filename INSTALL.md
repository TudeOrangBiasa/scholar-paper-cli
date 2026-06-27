# Install

One-step install for `scholar-paper-mcp`. Suitable for AI agents.

## Requirements

- Python 3.13
- uv 0.10+
- git (with git-lfs 3.0+)
- ~150MB disk (model bundled via git LFS)

## Install

```bash
# Clone (auto-fetches model via git LFS)
git clone https://github.com/TudeOrangBiasa/scholar-paper-mcp
cd scholar-paper-mcp

# Install Python deps
uv sync

# Verify
uv run pytest -q          # 266 passed, 0 skipped
uv run python -c "import scholar_paper_mcp; print(scholar_paper_mcp.__version__)"  # 0.1.0
```

## Run (stdio transport)

```bash
uv run python -m scholar_paper_mcp
# or
uv run scholar-paper-mcp
```

Server uses stdio. Exits when stdin closes.

## OpenCode registration

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcpServers": {
    "scholar-paper-mcp": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/scholar-paper-mcp", "run", "scholar-paper-mcp"]
    }
  }
}
```

Replace `/absolute/path/to/scholar-paper-mcp` with the clone path. Restart OpenCode.

## Environment variables

Optional, set before `python -m scholar_paper_mcp`:

```bash
# Higher Semantic Scholar rate limits (free key at https://www.semanticscholar.org/product/api)
export SPM_API_KEY=your-key

# Skip API calls entirely (cache-only mode)
export SPM_OFFLINE_MODE=true
```

All env vars: see `docs/CONFIGURATION.md`.

## Verify MCP works in OpenCode

After registration, in OpenCode:

```
> list 15 papers about quantum entanglement
```

OpenCode should invoke `search_papers` tool. Check OpenCode logs for MCP server connection.

## Project layout (key paths)

| Path | Purpose |
|------|---------|
| `models/model_quantized.onnx` | mE5-small int8 ONNX, 113MB, git LFS |
| `models/tokenizer.json` | XLM-RoBERTa tokenizer, 16MB |
| `~/.local/share/scholar-paper-mcp/cache.db` | SQLite cache (created at runtime) |
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

**Tests show 9 skipped (model not downloaded)**

Same as above. LFS not pulled. Run `git lfs pull`.

**`SS API rate limited (429)`**

Without `SPM_API_KEY`: ~100 requests per 5 minutes shared pool. Set key for higher limits.

## Uninstall

```bash
# Remove clone
rm -rf /path/to/scholar-paper-mcp

# Remove cache
rm -rf ~/.local/share/scholar-paper-mcp

# Unregister from OpenCode
# Edit ~/.config/opencode/opencode.json, remove the scholar-paper-mcp entry
```

## Tests

```bash
uv run pytest -q                # all tests, 266 pass, 0 skip
uv run pytest tests/test_docs.py # doc consistency only
uv run ruff check src tests     # lint
uv run ty check src tests       # type check
uv run ruff format --check src tests  # format
```

All four must pass before committing.
