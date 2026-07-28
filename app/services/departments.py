"""Логика отделов: гарантировать дефолтный демо-отдел для быстрого онбординга."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.department import Department

DEFAULT_NAME = "Демо-отдел"


async def get_or_create_default(db: AsyncSession) -> Department:
    """Вернуть первый отдел или создать дефолтный, если отделов ещё нет."""
    existing = (await db.execute(select(Department).limit(1))).scalars().first()
    if existing is not None:
        return existing
    dept = Department(name=DEFAULT_NAME)
    db.add(dept)
    await db.flush()
    await db.refresh(dept)
    return dept
