---
name: security-hardening
description: Security implementation and audit playbook — auth, OWASP Top 10, secrets, webhooks, uploads, rate limiting, supply chain. Use PROACTIVELY whenever implementing or reviewing auth, user input, file uploads, payments, webhooks, outbound URL fetching, or when the user mentions security, безопасность, взлом, уязвимости.
---

# Security Hardening

## Auth

- Passwords: argon2id (or bcrypt cost ≥12); constant-time compare; generic "invalid credentials" errors; rate limit + lockout with backoff on login.
- Sessions/tokens: short-lived access (≤15m) + rotating refresh with reuse detection; httpOnly+Secure+SameSite cookies preferred over localStorage; logout revokes refresh.
- Authorization at the **service layer**, deny-by-default; object-level checks on every ID from the client (IDOR is the #1 real-world bug). Roles/permissions in one place, not sprinkled ifs.
- OAuth: state + PKCE; validate `iss`/`aud`/`exp` on every JWT; pin algorithms (no `alg: none`).

## Input & injection

- Parameterized queries ONLY (ORM or placeholders). No string-built SQL, shell commands, or eval on user data — ever.
- Schema-validate every boundary (zod/pydantic): types, lengths, enums, and *strip unknown keys* (kills mass assignment).
- File uploads: allowlist MIME + magic-bytes check, size cap, randomized storage names outside webroot / in object storage, never trust client filename or Content-Type.
- Path ops: resolve + verify prefix before touching filesystem with user-influenced paths.

## Web layer

- Headers: CSP (start strict, loosen deliberately), HSTS, X-Content-Type-Options: nosniff, Referrer-Policy, frame-ancestors.
- CORS: explicit origin list; never `*` with credentials.
- CSRF tokens for cookie-authenticated mutations (or strict SameSite + custom-header check for APIs).
- Open redirects: allowlist redirect targets.
- SSRF: user-supplied URLs fetched server-side → allowlist hosts, block private IP ranges (incl. after DNS resolution), timeouts, no redirects-to-private.

## Secrets & supply chain

- Secrets only via env/secret manager; `.env` in `.gitignore`; hooks in this profile block committing them — don't fight it.
- Never log tokens/passwords/full PII; scrub error reporters.
- Lockfiles committed; CI runs `npm audit` / `pip-audit`; review postinstall scripts; pin GitHub Actions by SHA for sensitive repos.

## Telegram / webhooks

- Incoming webhooks: verify signatures (Stripe-style HMAC, Telegram `secret_token`); reject stale timestamps; process idempotently by event id.
- Mini App `initData`: validate HMAC server-side per request — it IS your auth boundary.

## Rate limiting & DoS

- Rate limit: login, signup, password reset, OTP, search, anything expensive. Per-IP AND per-account.
- Pagination caps server-side; timeouts on all outbound calls; body size limits; regexes checked for catastrophic backtracking.

## Exit question for every loop

"How would I attack this?" — write the top 3 attack attempts and confirm each is dead. If you can't kill one, it's a finding, not a footnote.
