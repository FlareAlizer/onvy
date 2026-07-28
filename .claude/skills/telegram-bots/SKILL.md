---
name: telegram-bots
description: Production Telegram bot platform engineering — grammY/aiogram architecture, webhooks, FSM dialogs, keyboards, payments, Mini Apps, rate limits. Use PROACTIVELY for any Telegram bot or Mini App task, and whenever the user mentions бот, telegram, tg, inline keyboard, webhook, WebApp.
---

# Telegram Bots (Production)

## Stack & mode

TS → **grammY** (+ @grammyjs/conversations, runner); Py → **aiogram 3** (Router, FSM + RedisStorage). Prod = **webhook** behind HTTPS with `secret_token` verified on every update; long polling only in dev. Respond to webhook <1s: ack fast, push heavy work to a queue (BullMQ/arq).

## Architecture

Bot ≠ script. handlers (transport, thin) → services (logic) → repos (DB) → infra. Middleware order: request-id/logging → user loading/upsert → i18n → rate-limit → routers. One router/composer per feature. Session/FSM state in Redis, never in-memory in prod (restarts, multiple replicas).

## Telegram reality checklist

- **429**: respect `retry_after`, queue outbound sends per chat (~1 msg/s per chat, 30/s global), use a throttler (grammY transformer / aiogram middleware).
- **403 bot blocked**: mark user inactive, don't crash broadcasts; broadcasts always via queue with progress + resume.
- Message limits: text 4096, caption 1024 — split gracefully; entities break on naive slicing (split by paragraphs).
- `callback_query` MUST be answered (even empty) or clients show spinner.
- `callback_data` ≤64 bytes: compact codec (`"ord:cancel:1234"` / grammY callback-data plugin), version the schema, validate on parse (users replay old buttons).
- Edits: prefer editMessageText for wizard UIs to avoid chat spam; handle "message is not modified".
- Deep links: `/start payload` for referrals/auth handoff; validate payload.
- Media: use file_id for re-sends (don't re-upload); download via getFile only when processing.

## Dialogs (FSM)

Multi-step input = explicit states with: cancel command working at EVERY step, timeout/expiry, validation per step with re-prompt, summary+confirm before commit. Never parse free text into a 12-branch if-tree.

## Payments & Stars

pre_checkout answered <10s after real validation (stock, amounts). Fulfillment idempotent by `telegram_payment_charge_id`. Store full successful_payment payload. Refund path implemented, not "later".

## Mini Apps (WebApp)

`initData` validated server-side (HMAC per docs) on EVERY API request — it is the auth boundary; issue your own short-lived session after. Theme params respected; viewport via Telegram SDK; test in actual clients (iOS/Android/Desktop render differently).

## Ops

Webhook health: getWebhookInfo checked in /ready; alert on pending_update_count growth. Commands registered via setMyCommands per locale/scope. Bot token per environment; test bot for staging. Verification loop: fixture-update tests for critical handlers + smoke on test bot.
