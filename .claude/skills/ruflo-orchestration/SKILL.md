---
name: ruflo-orchestration
description: Orchestrating multi-agent swarms and persistent memory with ruflo (claude-flow) — when to swarm, topology, agent spawning via Task tool, memory discipline, learning loop. Use PROACTIVELY for multi-domain features, large refactors, parallel research, and whenever the user mentions swarm, рой, агенты, оркестрация, ruflo, or параллельно.
---

# Ruflo Orchestration

Ruflo = the harness: swarms, persistent HNSW-indexed memory, learned routing, hooks. Assumes `npx ruflo init` done (setup.sh). Health: `npx ruflo doctor --fix`.

## When to swarm (and not)

Swarm: feature spans API+DB+UI, refactor across many files, parallel research/audit, full delivery pipeline (/ship). Don't swarm: one-shot edits, single-file fixes, quick questions — orchestration overhead loses.

## Golden rule: 1 MESSAGE = ALL RELATED OPERATIONS

- Batch ALL todos in one TodoWrite (5–10+).
- Init swarm via MCP AND spawn ALL agents via Task tool in the SAME message. MCP coordinates; **Task-tool agents do the actual work** — never expect MCP calls alone to execute anything.
- Batch file reads/writes, batch memory ops, batch bash.
- Never poll swarm status in a loop — wait for results.

## Standard delivery topology (hierarchical)

```
architect (plan, contracts, loop decomposition)
  ├─ parallel: backend-engineer · frontend-engineer · db-engineer · telegram-bot-engineer (as needed)
  ├─ parallel after build: test-engineer · security-auditor · design-reviewer · perf-engineer (as needed)
  └─ code-reviewer merges verdicts → report
```
Mesh topology only for open-ended research (researcher x N with different angles). Each spawned agent gets: its loop spec, file scope, Definition of Done, verification command — self-contained, no "see above".

## Memory discipline (the LEARN phase)

- Session start: `mcp__claude-flow__memory_search` for the areas you'll touch (`project/<area>/*`) — don't re-learn what a past session paid for.
- Loop close: `memory_store` non-obvious learnings — decisions + why, gotchas, rejected approaches. Namespaced keys `project/<area>/<topic>`; research under `research/<topic>`.
- Big context about to compact? Store a session summary first.

## Useful commands

`npx ruflo doctor --fix` · `npx ruflo discover-plugins` · `npx ruflo plugins list` · `npx ruflo mcp list`. Key MCP namespaces: `memory_*`, `swarm_*`, `agent_spawn`, `task_*`, `hooks_*`.

## Anti-patterns

Spawning agents sequentially across messages · MCP-only "execution" (nothing runs) · unnamespaced memory dumping · swarming a 5-line fix · re-checking status every turn.
