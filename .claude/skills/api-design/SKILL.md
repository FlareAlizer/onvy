---
name: api-design
description: REST/HTTP API contract design — resources, errors, pagination, versioning, idempotency, webhooks, OpenAPI. Use PROACTIVELY before implementing any new endpoint or public contract, and when the user mentions API, endpoints, контракт, or integration surfaces.
---

# API Design

Contract first: schema (zod/pydantic/OpenAPI) before implementation.

## Shape
- Resource-oriented: plural nouns (`/users`, `/orders/{id}`), nesting ≤2, verbs only for true actions (`POST /orders/{id}/cancel`).
- Methods: GET safe/cacheable, PUT idempotent full-replace, PATCH partial, DELETE idempotent. 201+Location on create, 204 on delete.
- Timestamps ISO-8601 UTC (`2026-07-28T12:00:00Z`); IDs opaque strings; money as integer minor units + currency code, never floats.

## Errors — one envelope everywhere
```json
{ "error": { "code": "validation_failed", "message": "Email is invalid", "details": [{"path": "email", "issue": "format"}] } }
```
Codes machine-readable snake_case; statuses honest: 400 malformed, 401 unauthenticated, 403 unauthorized, 404 hidden-or-missing, 409 conflict, 422 semantic validation, 429 rate limited (+Retry-After), 500 never with internals.

## Collections
- Pagination mandatory: cursor-based (`?cursor=...&limit=`) for feeds/infinite scroll; page-based for admin tables. Server-side max limit. Response: `{ items, next_cursor | page_info }`.
- Filtering/sorting: explicit allowlisted params (`?status=active&sort=-created_at`). Never pass raw query fragments.

## Reliability
- `Idempotency-Key` header on POSTs with side effects worth money; store key→response for replay.
- Versioning: `/v1` prefix; additive = same version; breaking = new version + deprecation window documented.
- Webhooks you emit: HMAC-signed, timestamped, event id for consumer idempotency, retries with exponential backoff, dead-letter after N.

## Deliverable
Typed schema module or OpenAPI fragment + one consumer snippet (auth → call → handle error). Keep contract and implementation in the same PR so they can't drift.
