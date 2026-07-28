---
name: db-and-data
description: Database engineering — PostgreSQL schema design, migrations, indexing, transactions, N+1s, Redis caching, data integrity. Use PROACTIVELY for schema changes, slow queries, data modeling, and whenever the user mentions база, БД, database, миграции, Postgres, Redis, or query performance.
---

# DB & Data

## Schema

- Integrity lives in the DB, not only app code: FKs, NOT NULL, CHECK, UNIQUE. `timestamptz` always; `created_at/updated_at` on business tables; soft-delete (`deleted_at`) where history matters.
- IDs: uuid v7 (time-ordered) or bigint identity — pick per project, once. Money: numeric or integer minor units, never float. Enums: DB enums for truly closed sets, else text + CHECK.
- Normalize until it hurts, denormalize where a measured read path demands it (record why in the migration comment).

## Migrations

- All schema change via migration files (Prisma/Drizzle/Alembic). Reversible where feasible; destructive changes need explicit backfill + rollback plan in the PR.
- Expand-migrate-contract for zero-downtime: add new column → dual-write/backfill → switch reads → drop old, across deploys.
- Verify: applies UP and DOWN on scratch DB before merge (hook/CI enforces).

## Queries

- Index for real access patterns; composite index column order = equality → range; partial indexes for hot filtered subsets. Justify each index in a comment.
- EXPLAIN ANALYZE anything suspicious; seq scan on a large hot table = finding.
- N+1: any query inside a loop, any ORM lazy-load chain in a list view → join/include/dataloader.
- Pagination: keyset (cursor) for large/moving sets; OFFSET only for small admin tables.
- Transactions wrap multi-step writes; keep them short (no external HTTP inside a tx); pick isolation deliberately when it matters (e.g. `SERIALIZABLE` or `SELECT ... FOR UPDATE` for counters/stock).

## Redis

Cache-aside with explicit TTL + written invalidation strategy; keys namespaced `app:entity:id`. Redis is never the source of truth. Also fine for: rate-limit counters, FSM/session state, queues (BullMQ/arq), pub/sub. Eviction policy set consciously (`allkeys-lru` for pure cache, `noeviction` for queues — never mix on one instance).

## Ops floor

Connection pooling sized to DB limits; slow-query log on; automated backups WITH a tested restore script (untested backup = no backup).
