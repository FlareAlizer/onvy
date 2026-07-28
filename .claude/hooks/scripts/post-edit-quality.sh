#!/usr/bin/env bash
# PostToolUse hook for Write|Edit: best-effort format + fast checks. Always exits 0 (never blocks a turn).
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import json,sys;d=json.load(sys.stdin);t=d.get('tool_input') or {};print(t.get('file_path') or t.get('path') or '')" 2>/dev/null)
[ -z "$FILE" ] || [ ! -f "$FILE" ] && exit 0
case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx|*.json|*.css|*.md)
    if [ -f node_modules/.bin/prettier ]; then node_modules/.bin/prettier --write "$FILE" >/dev/null 2>&1; fi
    ;;
  *.py)
    command -v ruff >/dev/null 2>&1 && { ruff format "$FILE" >/dev/null 2>&1; ruff check --fix "$FILE" >/dev/null 2>&1; }
    ;;
esac
# лёгкие смелл-предупреждения (не блокируют)
case "$FILE" in
  *.ts|*.tsx|*.js|*.jsx)
    if grep -nE "console\.log\(" "$FILE" >/dev/null 2>&1 && ! echo "$FILE" | grep -qE "(test|spec|script)"; then
      echo "note: console.log left in $FILE — replace with the project logger before closing the loop."
    fi
    ;;
esac
exit 0
