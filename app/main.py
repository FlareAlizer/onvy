"""Точка входа приложения Onvy.

Схема базы накатывается миграциями отдельным шагом деплоя, а не на старте:
при нескольких воркерах старт превратился бы в гонку за одну и ту же схему.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.adapters.gigaam.speech import GigaAMSpeechRecognition
from app.api import (
    auth,
    comms,
    insights,
    kpi,
    menu,
    signup,
    staff,
    stop_list,
    training,
    voice,
)
from app.config import settings
from app.services import runtime

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Поднять шину связи на старте и аккуратно погасить на остановке."""
    from app.deps import get_redis_client

    redis = get_redis_client()
    app.state.redis = redis
    await runtime.get_bus(redis).start()
    logger.info(
        "Onvy поднят: ASR=%s, запасной=%s, языки GigaAM=%s",
        settings.asr_provider,
        settings.asr_fallback_provider or "нет",
        settings.gigaam_languages,
    )
    try:
        yield
    finally:
        await runtime.shutdown()
        await redis.aclose()


app = FastAPI(
    title="Onvy API",
    description="Голосовой ассистент, связь и перевод для линейного персонала",
    version="0.3.0",
    lifespan=lifespan,
)

for module in (auth, signup, voice, comms, menu, stop_list, insights, kpi, staff, training):
    app.include_router(module.router, prefix="/api")


@app.get("/health", tags=["system"])
async def health() -> dict[str, object]:
    """Живость сервиса и речевого стека.

    Ноду распознавания проверяем отдельно: на пилоте должно быть видно, работает
    ли ассистент, даже когда само приложение отвечает нормально.
    """
    node: bool | None = None
    if settings.gigaam_url:
        node = await GigaAMSpeechRecognition().healthy()
    return {
        "status": "ok",
        "asr_provider": settings.asr_provider,
        "asr_fallback": settings.asr_fallback_provider or None,
        "gigaam_node": node,
        "yandex": settings.yandex_enabled,
    }


# SPA официанта и управляющего.
def mount_spa(app: FastAPI, dist: Path) -> None:
    """Отдавать собранное приложение официанта и управляющего.

    Кэширование здесь не украшение, а защита от белого экрана в смене. Файлы
    сборки названы по содержимому (`index-CaCrevax.js`), поэтому кэшируются
    навсегда: другое содержимое — другое имя. А `index.html` указывает на эти
    имена, и старые файлы после выката удаляются, — телефон, закэшировавший его
    надолго, запросил бы несуществующий файл и показал белый экран посреди
    смены, без возможности объяснить официанту, что нажать. Поэтому индекс
    берётся с сервера при каждом открытии — он весит около полукилобайта, и
    экономить на нём нечего, а вся тяжёлая часть лежит в кэше навсегда.
    """
    from fastapi.staticfiles import StaticFiles

    class ImmutableAssets(StaticFiles):
        async def get_response(self, path: str, scope):  # type: ignore[override]
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response

    app.mount("/assets", ImmutableAssets(directory=dist / "assets"), name="spa-assets")

    index_headers = {"Cache-Control": "no-cache"}

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(dist / "index.html", headers=index_headers)

    # Прямые ссылки внутри приложения отдаём индексу, чтобы работала навигация,
    # а /api и /ws остаются за приложением — они объявлены выше.
    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        return FileResponse(dist / "index.html", headers=index_headers)


if FRONTEND_DIST.exists():
    mount_spa(app, FRONTEND_DIST)
