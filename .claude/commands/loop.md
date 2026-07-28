---
description: Run one full engineering loop (SPEC→PLAN→BUILD→VERIFY→LEARN) on a task
argument-hint: "<task or spec file>"
---
Run ONE full loop per the `loop-engineering` skill on: $ARGUMENTS.
1. SPEC: find or create the spec; grill me if ambiguous.
2. PLAN: if the task decomposes into multiple loops, list them and pick the first; delegate to the right subagent if specialized.
3. BUILD: implement only this loop's scope.
4. VERIFY: run real verification (typecheck/lint/tests; UI at 360/768/1280; migrations up+down) and paste actual output.
5. LEARN: store non-obvious learnings in ruflo memory; update the plan (check off the loop, append discovered loops).
Max 3 self-repair iterations on failure, then report honestly.
