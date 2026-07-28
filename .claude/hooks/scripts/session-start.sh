#!/usr/bin/env bash
# SessionStart hook: loop-engineering reminder + ruflo presence check. Always exit 0.
echo "Loop engineering active: SPEC -> PLAN -> BUILD -> VERIFY -> LEARN. No un-looped work, no vibe-verification."
if [ -d ".claude-flow" ] || [ -f "claude-flow.config.json" ]; then
  echo "ruflo detected: search memory for areas you will touch (memory_search 'project/...') before re-learning anything."
else
  echo "ruflo not initialized here: for multi-agent work run 'npx ruflo init' (see setup.sh)."
fi
[ -d specs ] && ls specs/*.md >/dev/null 2>&1 && echo "Open specs: $(ls specs/*.md | tr '\n' ' ')"
exit 0
