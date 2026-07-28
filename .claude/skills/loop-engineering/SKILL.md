---
name: loop-engineering
description: The core working discipline of this profile — decompose any non-trivial development task into verifiable loops (SPEC → PLAN → BUILD → VERIFY → LEARN). Use PROACTIVELY for every feature, refactor, bugfix, or bot/app build, whenever work spans more than one file or one obvious edit, and whenever the user says "loop", "цикл", "по циклу", or asks to plan work.
---

# Loop Engineering

A **loop** is the smallest unit of work that can be independently specified, built, and *verified with evidence*. You never ship un-looped work.

## The cycle

1. **SPEC** — the requirement, unambiguous. If the request is fuzzy: run the `grilling` skill until an implementer could build it without asking a question. Persist to `specs/<name>.md`:
   - Goal (one sentence) · Non-goals · Constraints · Acceptance criteria (checkable) · Open questions (must be empty before BUILD).
2. **PLAN** — split into loops. Each loop: ≤ ~1–2 hours of work, one owner (you or a subagent), one verification command/procedure. Order by dependency; parallelize independent loops via ruflo swarm (skill `ruflo-orchestration`).
3. **BUILD** — implement exactly one loop. Resist scope creep: anything discovered mid-loop becomes a NEW loop in the plan, not a detour.
4. **VERIFY** — evidence, not vibes:
   - code: typecheck + lint + tests green (paste real output, not "should pass")
   - UI: rendered at 360/768/1280, states checked (loading/empty/error)
   - bot: handler fixture test or live smoke on test token
   - migration: applies up AND down on scratch DB
5. **LEARN** — store the non-obvious in ruflo memory (`memory_store`, key `project/<area>/<topic>`): gotchas, decisions, why-nots. Next session starts by `memory_search`-ing the area it touches.

## Loop states & repair

- VERIFY fails → back to BUILD with the failure as input. **Max 3 self-repair iterations**, then STOP and report honestly: what's broken, what was tried, best hypothesis. Never fake green, never weaken the test to pass it.
- A loop with an unresolved user-owned decision is BLOCKED, not guessed. Surface it.

## Definition of Done (per loop)

- [ ] Acceptance criteria of this loop met
- [ ] Verification output shown (real)
- [ ] No silent TODOs / commented-out code left
- [ ] Learnings stored (if any)
- [ ] Plan updated (loop checked off, new loops appended)

## Anti-patterns

- "Big bang": building the whole feature then testing at the end.
- "Vibe-verified": claiming done without running anything.
- "Detour spiral": fixing unrelated things mid-loop — log them as loops instead.
- "Groundhog session": re-learning what a past session already learned — that's a memory-discipline failure.
