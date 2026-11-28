#!/usr/bin/env bash
# Rebuild bssmacro-standalone/ — a self-contained git repo with just the
# Bee Swarm Simulator macro — from the live bssmacro/ package.
#
# Run this after making changes to bssmacro/ so the standalone copy stays
# in sync (it commits the diff inside the standalone repo automatically).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/bssmacro"
DST="$ROOT/bssmacro-standalone"

if [ ! -d "$DST/.git" ]; then
  echo "error: $DST is not a git repo (bootstrap it first)" >&2
  exit 1
fi

# 1) fresh copy of the package (code, tests, templates, docs, requirements)
rm -rf "$DST/bssmacro"
cp -r "$SRC" "$DST/bssmacro"

# 2) root-level files that mirror the package docs
cp "$SRC/README.md" "$DST/README.md"

# 3) clean caches out of the copy
find "$DST" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# 4) commit inside the standalone repo if anything changed
cd "$DST"
# fresh copies of this workspace may lack git identity — set it if missing
git config user.name  >/dev/null 2>&1 || git config user.name "fak3hidden"
git config user.email >/dev/null 2>&1 || \
  git config user.email "260537140+fak3hidden@users.noreply.github.com"
git add -A
if git diff --cached --quiet; then
  echo "standalone repo already up to date"
else
  git commit -m "Sync bssmacro from workspace"
  echo "standalone repo updated"
fi
