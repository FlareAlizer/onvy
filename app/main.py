import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    analytics,
    assistant,
    comms,
    courses,
    dashboard,
    departments,
    employees,
    goals,
    products,
    voice,
)
from app.config import settings
from app.db import init_db

logging.basicConfig(level=logging.INFO)

WEB_DIR = Path(__file__).parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Создать таблицы на старте (для MVP; в проде — Alembic)."""
    await init_db()
    if not settings.yandex_enabled:
        logging.warning(
            "YANDEX_API_KEY/YANDEX_FOLDER_ID не заданы — голосовые роуты вернут 503, "
            "перевод работает в режиме заглушки."
        )
    yield


app = FastAPI(
    title="Onvy MVP API",
    description="Реалтайм-голосовой ассистент + связь для линейного персонала",
    version="0.2.0",
    lifespan=lifespan,
)

_ROUTERS = (
    employees,
    departments,
    products,
    assistant,
    comms,
    voice,
    goals,
    dashboard,
    analytics,
    courses,
)
for module in _ROUTERS:
    app.include_router(module.router, prefix="/api")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Проверка живости сервиса."""
    return {"status": "ok", "yandex": "on" if settings.yandex_enabled else "off"}


# Веб-клиенты. Основной — React SPA (frontend/dist), если собран; иначе
# фолбэк на старые vanilla-страницы. Старые /worker /rop /me остаются как legacy.
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="spa-assets")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    if FRONTEND_DIST.exists():
        return FileResponse(FRONTEND_DIST / "index.html")
    return FileResponse(WEB_DIR / "index.html")


@app.get("/worker", include_in_schema=False)
async def worker_page() -> FileResponse:
    return FileResponse(WEB_DIR / "worker.html")


@app.get("/rop", include_in_schema=False)
async def rop_page() -> FileResponse:
    return FileResponse(WEB_DIR / "rop.html")


@app.get("/me", include_in_schema=False)
async def employee_page() -> FileResponse:
    return FileResponse(WEB_DIR / "employee.html")
