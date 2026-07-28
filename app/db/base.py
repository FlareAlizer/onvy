from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Именование ограничений — фиксируем заранее, иначе Alembic autogenerate
# даёт разные случайные имена индексов/constraint'ов на разных прогонах,
# и down-миграции для них становится больно писать вручную.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей домена.

    Схема управляется только через Alembic (alembic/versions) — нигде в
    рантайме нет и не должно быть Base.metadata.create_all().
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
