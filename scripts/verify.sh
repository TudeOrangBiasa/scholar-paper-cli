#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
step() { printf '\n==> %s\n' "$1"; }
step "uv sync (locked)"; uv sync --locked -q
step "pytest"; uv run python -m pytest -q
step "ruff check"; uv run ruff check src tests
step "ty check"; uv run ty check src tests
step "ruff format --check"; uv run ruff format --check src tests
step "security scan (trivy fs)"
if command -v trivy >/dev/null 2>&1; then
  trivy fs --scanners vuln,secret,config --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --quiet .
else
  echo "    skipped: trivy not installed"
fi
if [ "${VERIFY_SKIP_SMOKE:-0}" != "1" ]; then
  step "CLI smoke (verify-spm)"; bash skills/verify-spm/scripts/smoke.sh
fi
printf '\nverify: all gates passed\n'
