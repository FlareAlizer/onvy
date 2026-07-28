---
name: tdd-verification
description: Testing and verification discipline — TDD flow, test pyramid, integration with real containers, E2E, regression tests, honest reporting. Use PROACTIVELY when implementing domain logic, fixing bugs, closing a loop's VERIFY phase, or when the user mentions tests, тесты, coverage, TDD, or "проверь что работает".
---

# TDD & Verification

Verification is evidence. "Should work" is not a state a loop can end in.

## TDD flow (domain logic)

Red → Green → Refactor: write the failing test that encodes the spec's acceptance criterion, watch it fail for the RIGHT reason, implement minimally, refactor with green bar. If you can't write the test first, the spec is fuzzy — go grill.

## Pyramid

- **Unit** (many, <10ms each): domain logic, pure functions, validators. No I/O.
- **Integration** (solid layer): API endpoints & repos against REAL containerized Postgres/Redis (testcontainers or docker-compose test profile). Migrations run in test setup — schema drift dies here.
- **E2E** (few): Playwright happy paths + the one critical auth/money flow. Stable selectors (data-testid), no sleeps.
- Mock ONLY true externals (Stripe, Telegram API, email) with contract-shaped fakes; never mock your own DB "for speed".

## Rules

- One behavior per test; name = the behavior ("rejects expired token", "splits 4097-char message"). Arrange-Act-Assert.
- Deterministic: fake timers, seeded data, no shared mutable state between tests, no order dependence.
- Bug fix protocol: reproduce as failing test FIRST → fix → test green → both committed together.
- Never weaken an assertion to make it pass; never `skip` silently — a skipped test carries a comment with a ticket/reason.
- Factories/builders for data; fixtures only for genuinely static reference data.
- Flaky = quarantine + investigate; retry-until-green is lying with extra steps.

## Honest reporting (loop VERIFY)

Paste real output: test counts, failures verbatim, typecheck/lint results. If something is red, the loop is open — say so. Faked green is the one unforgivable sin in this profile.
