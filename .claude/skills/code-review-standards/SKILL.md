---
name: code-review-standards
description: Code review discipline — what to check, in what order, how to write findings, when to block. Use when reviewing any diff/PR, before merges, and whenever the user asks "посмотри код", "сделай ревью", review this, or check my changes.
---

# Code Review Standards

Review the diff, not the whole repo. Priorities in order — stop padding once real issues are found:

1. **Correctness vs spec**: does it do what the loop's spec says? Edge cases: empty/null/zero, unicode/long input, concurrency, duplicate submits, timezone.
2. **Error paths**: swallowed exceptions, catch-and-log-and-continue on critical paths, missing rollback on partial failure.
3. **Boundaries**: unvalidated input crossing in, internals leaking out (stack traces, IDs, PII in logs).
4. **Architecture conformance**: layering intact, no domain→transport imports, config via env, no copy-paste module that ignores existing shared code.
5. **Security smells**: string-built queries, raw user data in shell/paths/HTML, new endpoints without authz, secrets in code → escalate to security-auditor, never approve past them.
6. **Tests**: would they fail if the feature broke? Regression test present for bug fixes? Any weakened/skipped assertions?
7. **Maintainability**: naming honesty, dead code, duplication past rule-of-three, 400+ line files, comments that lie.

## Verdicts

- **BLOCK**: any Critical/High security issue, faked green (skipped/weakened tests, hardcoded happy path), data-loss risk.
- **REQUEST CHANGES**: correctness or boundary issues.
- **APPROVE**: clean, or nits only (state nits, approve anyway).

## Finding format

`file:line — issue — why it matters (one sentence, concrete consequence) — suggested fix`. No style nits a formatter catches. No "consider maybe possibly" hedging — recommend or stay silent. If clean: say so in ≤2 sentences and stop.
