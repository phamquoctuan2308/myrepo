#!/usr/bin/env bash
# Cross-platform Python launcher for AI log hooks.
# Resolve project virtual environments from this script's location first, then
# fall back to validated interpreters on PATH.
# Usage: bash scripts/_pyrun.sh <script> [args...]
set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

for candidate in \
  "$REPO_ROOT/.venv/Scripts/python.exe" \
  "$REPO_ROOT/.venv/bin/python" \
  "$REPO_ROOT/.ai-log/.venv/Scripts/python.exe" \
  "$REPO_ROOT/.ai-log/.venv/bin/python"; do
  if [ -x "$candidate" ] && "$candidate" -c "import sys" >/dev/null 2>&1; then
    exec "$candidate" "$@"
  fi
done

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 \
    && "$candidate" -c "import sys" >/dev/null 2>&1; then
    exec "$candidate" "$@"
  fi
done

if command -v py >/dev/null 2>&1 && py -3 -c "import sys" >/dev/null 2>&1; then
  exec py -3 "$@"
fi

printf '%s\n' 'AI log hook: no usable Python interpreter was found.' >&2
exit 0
