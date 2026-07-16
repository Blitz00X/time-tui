#!/usr/bin/env bash
# Run CSS validation + brief todo startup; write combined report.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORT="$ROOT/css_check_report.txt"
{
  echo "=== validate_css.py ==="
  echo "cmd: $ROOT/.venv/bin/python $ROOT/scripts/validate_css.py"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/validate_css.py" 2>&1
  echo "exit: $?"
  echo ""
  echo "=== todo startup (2s) stderr ==="
  echo "cmd: timeout 2 $ROOT/.venv/bin/python -m todo.cli"
  timeout 2 "$ROOT/.venv/bin/python" -m todo.cli 2>&1 | head -100 || true
  echo "exit: $?"
} >"$REPORT" 2>&1
echo "Wrote $REPORT"
