#!/usr/bin/env bash
# ============================================================
# Установка профиля в проект + подключение ruflo и скилл-паков
# Запускать из корня проекта: bash /path/to/claude-dev-profile/setup.sh
# ============================================================
set -e
PROFILE_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(pwd)"

echo "==> 1/5 Копирую профиль в $PROJECT_DIR"
mkdir -p .claude
cp -r "$PROFILE_DIR/.claude/." .claude/
# CLAUDE.md не перетираем молча
if [ -f CLAUDE.md ]; then
  cp "$PROFILE_DIR/CLAUDE.md" CLAUDE.profile.md
  echo "    CLAUDE.md уже существует — профиль записан в CLAUDE.profile.md (смерджи вручную)."
else
  cp "$PROFILE_DIR/CLAUDE.md" CLAUDE.md
fi
mkdir -p specs docs
chmod +x .claude/hooks/scripts/*.sh .claude/hooks/scripts/*.py 2>/dev/null || true

echo "==> 2/5 Инициализирую ruflo (оркестрация роя + память + learning loop)"
if command -v node >/dev/null 2>&1; then
  npx --yes ruflo init || echo "    ruflo init не прошёл — запусти вручную: npx ruflo init"
  npx --yes ruflo doctor --fix || true
else
  echo "    Node.js не найден — поставь Node 20+ и запусти: npx ruflo init && npx ruflo doctor --fix"
fi

echo "==> 3/5 Ставлю сторонние скилл-паки (дизайн-чутьё и инженерные практики)"
# Через npx skills (agent-agnostic installer). Каждый — best-effort.
if command -v node >/dev/null 2>&1; then
  npx --yes skills add pbakaus/impeccable --yes            || echo "    [skip] impeccable"
  npx --yes skills add leonxlnx/taste-skill --yes          || echo "    [skip] taste-skill"
  npx --yes skills add emilkowalski/skills --yes           || echo "    [skip] emilkowalski/skills"
  npx --yes skills add hardikpandya/stop-slop --yes        || echo "    [skip] stop-slop"
  npx --yes skills add mattpocock/skills --yes             || echo "    [skip] mattpocock/skills"
  npx --yes skills add Graphify-Labs/graphify --yes        || echo "    [skip] graphify"
fi

echo "==> 4/5 Альтернатива через Claude Code plugin marketplace (выполни в сессии Claude Code):"
cat << 'CMDS'
    /plugin marketplace add ruvnet/ruflo
    /plugin install ruflo-core@ruflo
    /plugin install ruflo-swarm@ruflo
    /plugin install ruflo-rag-memory@ruflo
    /plugin marketplace add pbakaus/impeccable
    /plugin install impeccable@impeccable
    /plugin marketplace add leonxlnx/taste-skill
    /plugin marketplace add mattpocock/skills
CMDS

echo "==> 5/5 Готово. Проверь: claude → /agents (14 агентов), /help (команды), skills подхватятся автоматически."
echo "Первый шаг в новом проекте: /grill-me <идея> → /spec → /ship"
