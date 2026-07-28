from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import engine

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Зависимость FastAPI: одна сессия/транзакция на запрос.

    Коммит при успешном завершении обработчика; откат и проброс исключения
    дальше, если обработчик упал — сессия никогда не остаётся в подвешенном
    состоянии на совести вызывающего кода.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
