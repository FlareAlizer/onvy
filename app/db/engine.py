from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import settings

# pool_size/max_overflow — под несколько uvicorn-воркеров на одной ноде пилота
# (VPS с одной GPU/CPU нодой, не кластер): 10 соединений на воркер с запасом
# в 5 сверху достаточно для нагрузки одной чайханы и не исчерпывает лимит
# Postgres по умолчанию (max_connections=100) при 2-4 воркерах.
# pool_pre_ping — Wi-Fi/сеть на VPS нестабильны меньше, чем в зале ресторана,
# но обрыв соединения с БД не должен валить запрос с невнятной ошибкой.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)
