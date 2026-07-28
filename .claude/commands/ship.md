---
description: Full delivery pipeline for a feature via ruflo swarm (plan → parallel build → parallel review → verdict)
argument-hint: "<feature or spec file>"
---
Deliver: $ARGUMENTS — using the `ruflo-orchestration` skill, end to end.
1. Ensure a done spec exists (grill me if not).
2. Spawn `architect` to produce the plan and loop decomposition.
3. In ONE message: init the swarm (MCP) and spawn ALL needed builders via Task tool in parallel (`backend-engineer`, `frontend-engineer`, `db-engineer`, `telegram-bot-engineer` — as the plan requires), each with a self-contained loop spec, file scope, DoD and verification command.
4. After build: spawn reviewers in parallel — `test-engineer` (gaps), `security-auditor`, `design-reviewer` (if UI), `perf-engineer` (if hot paths).
5. `code-reviewer` merges all verdicts into one report: SHIP / FIX LIST (ordered by severity).
6. Fix Critical/High items in repair loops (max 3 each), re-verify, store learnings in memory.
Never fake green. Final message: what shipped, evidence of verification, what's deferred and why.
