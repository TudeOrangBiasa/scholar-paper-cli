#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
RUN_DIR=".scratch/verify/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
export SPM_CACHE_PATH="$SCRATCH/cache.db" SPM_OFFLINE_MODE=true SPM_EMBEDDING_MODEL=none
uv run spm --version | tee "$RUN_DIR/version.txt"
uv run spm session list smoke | tee "$RUN_DIR/session-list.json"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["data"]==[] and d["meta"]["source"]=="db", d' "$RUN_DIR/session-list.json"
[ -f "$SPM_CACHE_PATH" ] || { echo "FAIL: cache db not created at SPM_CACHE_PATH"; exit 1; }
echo "smoke: ok (offline, isolated cache db created, stdout is JSON)"
echo "evidence: $RUN_DIR"
