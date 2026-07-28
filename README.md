# Claude Dev Profile — Production Full-Stack + Design + Loop Engineering

Профиль для Claude Code под **реальный прод** (не MVP): сайты, веб-приложения, платформы, Telegram-боты, адаптивный фронтенд и бэкенд. С дизайн-чутьём, безопасностью по умолчанию и оркестрацией роя агентов через **ruflo**.

## Установка

```bash
cd твой-проект
bash /путь/к/claude-dev-profile/setup.sh
```

Скрипт: копирует `.claude/` и `CLAUDE.md` в проект, запускает `npx ruflo init` (рой, память, learning loop), ставит сторонние скилл-паки, печатает команды для plugin-marketplace-варианта установки.

Требования: Node 20+, Python 3 (для хуков), git.

## Что внутри

### Ядро — CLAUDE.md
Loop-инженеринг как операционная система: **SPEC → PLAN → BUILD → VERIFY → LEARN**. Ни одна задача не закрывается без доказательств (реальные тесты/рендеры, не «должно работать»). Максимум 3 итерации самопочинки, потом честный отчёт. Прод-стандарты по архитектуре, безопасности и дизайну зашиты как правила, а не пожелания.

### 14 субагентов (`.claude/agents/`)
| Агент | Роль |
|---|---|
| `architect` | план, контракты, декомпозиция на лупы (opus) |
| `backend-engineer` | API, сервисы, домен, очереди |
| `frontend-engineer` | React/Next, токены, состояния, адаптив |
| `db-engineer` | схемы, миграции, индексы, N+1 |
| `telegram-bot-engineer` | grammY/aiogram, webhook, FSM, платежи, Mini Apps |
| `api-designer` | контракты до кода: схемы, ошибки, пагинация, идемпотентность |
| `security-auditor` | атакует код до атакующих; вердикт BLOCK/PASS (opus, read-only) |
| `code-reviewer` | ревью диффа, ловит fake green (opus, read-only) |
| `design-reviewer` | вкус: иерархия, токены, анти-слоп, 360/768/1280 (opus, read-only) |
| `test-engineer` | пирамида тестов, testcontainers, регрессии |
| `devops-engineer` | Docker, CI/CD, TLS, zero-downtime, бэкапы |
| `perf-engineer` | сначала меряет, потом чинит; before/after цифры |
| `docs-writer` | README/ADR/runbooks без слопа |
| `researcher` | сравнение библиотек, факты/оценки/гипотезы раздельно |

### 15 скиллов (`.claude/skills/`)
`loop-engineering` · `grilling` (прожарка спеки по одному вопросу) · `production-architecture` · `security-hardening` · `api-design` · `design-taste` (дизайн-рид, три диала, список запрещённых AI-дефолтов) · `ui-motion` (тайминги/пружины/reduced-motion по Эмилю Ковальскому) · `responsive-adaptive` · `telegram-bots` · `ux-writing` (анти-слоп по stop-slop) · `tdd-verification` · `db-and-data` · `deploy-and-ops` · `code-review-standards` · `ruflo-orchestration`

### 9 команд (`.claude/commands/`)
`/grill-me` — прожарить идею до буквально исполнимой спеки
`/spec` — оформить/дожать спеку
`/loop` — один полный луп на задачу
`/ship` — полный конвейер доставки фичи через рой ruflo
`/security-review`, `/design-review` — целевые аудиты
`/swarm` — явная оркестрация роя
`/verify` — честный прогон всех проверок с реальным выводом
`/handoff` — передача сессии без потери контекста

### Хуки (`.claude/hooks/` + `settings.json`)
- **guard-bash** (PreToolUse): блокирует `rm -rf /`, `curl | sh`, force-push в main, `git add .env`, `--no-verify`, `chmod 777`, `DROP DATABASE` в bash.
- **protect-secrets** (PreToolUse): блокирует запись реальных `.env` и захардкоженных ключей (OpenAI/Anthropic/GitHub/AWS/Telegram-токены, приватные ключи).
- **post-edit-quality** (PostToolUse): автоформат prettier/ruff, предупреждение про забытый `console.log`. Никогда не блокирует ход.
- **session-start**: напоминание про loop-протокол, проверка ruflo, список открытых спек.
- `permissions.deny` запрещает Claude читать `.env` и приватные ключи.

### Ruflo (оркестрация роя)
`npx ruflo init` даёт: MCP-сервер (memory_*, swarm_*, agent_spawn, task_*), персистентную память с семантическим поиском, learning loop, фоновых воркеров. Правила использования — в скилле `ruflo-orchestration` и §4 CLAUDE.md. Золотое правило: **1 сообщение = все связанные операции** (init роя + спавн всех агентов через Task tool разом). Память: `memory_search` в начале сессии, `memory_store` при закрытии лупа — это и есть фаза LEARN.

### Сторонние скилл-паки (ставятся setup.sh из оригинальных репо)
- **impeccable** (pbakaus) — глубокие дизайн-плейбуки: critique/audit/polish/animate/typeset/harden и др.
- **taste-skill** (leonxlnx) — анти-слоп лендинги/портфолио, дизайн-системы.
- **emilkowalski/skills** — apple-design, improve/review-animations, prototype, pick-ui-library.
- **stop-slop** (hardikpandya) — анти-слоп прозы (наш `ux-writing` — его дистиллят, полный пак глубже).
- **mattpocock/skills** — grilling, tdd, code-review, wayfinder, domain-modeling и др.
- **graphify** — граф знаний по кодовой базе: `/graphify` строит карту проекта, потом `graphify query` для вопросов по архитектуре.

Ставятся из первоисточников, а не копируются — чтобы получать обновления и не нарушать атрибуцию.

## Рабочий цикл (как этим пользоваться)

```
Идея → /grill-me → спека готова → /ship
                                    ├─ architect: план и лупы
                                    ├─ рой строит параллельно
                                    ├─ рой ревьюит параллельно (тесты/секьюрити/дизайн)
                                    └─ code-reviewer: вердикт → фиксы → /verify
Мелочь (1 файл) → /loop без роя
Перед мержем → /security-review + /design-review
Конец сессии → /handoff
```

## Что дальше (по желанию)
- Квант-профиль соберём отдельно на базе awesome-quant + Computational-Finance-Course, как договорились.
- Под конкретный стек проекта можно сузить дефолты в CLAUDE.md §3 (сейчас: Fastify/NestJS · FastAPI · Next.js · grammY/aiogram · Postgres · Redis).
