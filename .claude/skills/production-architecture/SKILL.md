---
name: production-architecture
description: Production-grade architecture rules for backend and full-stack systems — layering, boundaries, config, errors, observability, project structure. Use PROACTIVELY when starting a new project/service/bot, adding a major feature, restructuring code, or when the user mentions architecture, structure, "прод", scalability, or maintainability.
---

# Production Architecture

## Layering (default: pragmatic hexagonal)

```
transport (HTTP handlers / bot handlers / webhooks / CLI)
  → application (use-cases/services, orchestrates domain + infra)
    → domain (entities, business rules — pure, no I/O imports)
  → infrastructure (DB repos, HTTP clients, queues, cache) — behind interfaces
```

Hard rules: domain imports nothing from transport/infra. Transport is thin: parse → validate → call service → map result. Infra implements interfaces defined by application/domain.

## Project skeleton (TS backend example)

```
src/
  app.ts server.ts config.ts        # composition root; config validated (zod) at startup, crash loudly
  modules/<feature>/                 # feature-sliced
    <feature>.routes.ts  .service.ts  .repo.ts  .schemas.ts  .types.ts
  shared/{errors,logger,middleware,db,queue}/
tests/  specs/  docs/  scripts/
```

Same shape for Python (FastAPI routers/services/repositories) and bots (handlers ≙ transport).

## Non-negotiables

- **Config**: env only, validated at startup with schema; no `process.env` scattered through code; `.env.example` maintained.
- **Errors**: typed hierarchy (`DomainError`, `NotFoundError`, `ValidationError`, `ForbiddenError`…), one central handler mapping to transport codes; internals never leak to clients; unexpected errors logged with stack + request id.
- **Validation at every boundary**: HTTP input, bot updates, webhook payloads, queue messages, third-party responses you depend on.
- **Observability**: structured JSON logs in prod with request/update id; `/health` (liveness) and `/ready` (deps) endpoints; Sentry or equivalent from day one.
- **State changes**: transactions around multi-step writes; idempotency for retried operations; outbox pattern when events must not be lost.
- **Async**: anything > ~1s or retryable goes to a queue with backoff + dead-letter, not inline in the request.
- **Graceful shutdown**: SIGTERM → stop accepting → drain → close pools.

## Decision heuristics

- Monolith-first with clean module boundaries; extract services only under real pressure (team/scale), record as ADR.
- Boring tech wins: Postgres before exotic DBs; Redis for cache/queues; add infra only when a concrete requirement demands it.
- Every significant decision → one-page ADR (docs/adr/), including rejected options.
