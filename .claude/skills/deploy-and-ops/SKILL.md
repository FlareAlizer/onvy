---
name: deploy-and-ops
description: Deployment and operations — Docker, docker-compose, CI/CD with GitHub Actions, reverse proxy/TLS, zero-downtime deploys, backups, monitoring, environments. Use PROACTIVELY when a project approaches shipping, and whenever the user mentions deploy, деплой, VPS, docker, CI, hosting, домен, or production setup.
---

# Deploy & Ops

## Containers

- Multi-stage Dockerfile: build stage → slim runtime (distroless/alpine where sane), non-root USER, pinned base tags, HEALTHCHECK, .dockerignore. Build works from clean clone.
- docker-compose = dev parity: app + Postgres + Redis (+ mailhog) up with one command; volumes for data; `.env` from `.env.example`.

## CI (GitHub Actions)

PR pipeline, fail fast: install (cached) → lint → typecheck → tests with service containers → build → `npm audit`/`pip-audit`. Required check on main. Secrets via repo/environment secrets only.

## CD

Build once, promote the same image (tag = git sha). Config differs by environment ONLY via env vars. Migrations = explicit deploy step with a lock, before new code serves traffic (expand-contract for breaking changes). Rollback = redeploy previous tag + documented migration-down policy.

## Runtime (typical VPS/Docker target)

- Reverse proxy: Caddy (auto-TLS) or nginx+certbot; HTTP→HTTPS redirect, HSTS, gzip/brotli, security headers at the edge; proxy timeouts aligned with app.
- Zero-downtime: healthchecked rolling restart (compose `--wait` / systemd / swarm) or blue-green; app handles SIGTERM: stop accepting → drain → close pools.
- Telegram bots: webhook URL per environment; setWebhook in deploy script; staging bot ≠ prod bot token.

## Ops floor

- Backups: nightly pg_dump with retention + a tested `restore.sh`; test restore quarterly (or after schema epochs).
- Monitoring: uptime probe on /health, Sentry (backend+frontend), disk/mem alerts, log rotation, structured logs shipped or at least persisted.
- Runbook in docs/deploy.md: deploy, rollback, restore, rotate secrets — each a copy-pasteable command list.
- `.env.example` always current; new env var without it = review finding.
