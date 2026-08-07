#!/usr/bin/env bash
# Install this repo's skills (skills/*/SKILL.md) into an agent skills directory.
# Usage: ./skills.sh [TARGET_DIR]
#   default target: ~/.agents/skills   (override with SKILLS_DIR or the argument)
# Idempotent: re-running refreshes the installed copies.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-${SKILLS_DIR:-$HOME/.agents/skills}}"

if ! compgen -G "$REPO_DIR/skills/*/SKILL.md" > /dev/null; then
  echo "error: no skills found in $REPO_DIR/skills" >&2
  exit 1
fi

for skill in "$REPO_DIR"/skills/*/; do
  name="$(basename "$skill")"
  mkdir -p "$TARGET/$name"
  cp "$skill/SKILL.md" "$TARGET/$name/SKILL.md"
  echo "installed $name -> $TARGET/$name/SKILL.md"
done
