from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Product(Base):
    """Позиция каталога магазина — единица базы знаний ассистента.

    По этой таблице ассистент ищет ответ на голосовой запрос сотрудника
    («есть ли X», «сколько стоит Y», «что посоветовать вместо Z»).
    """

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(120), default="")
    price: Mapped[int] = mapped_column(default=0)  # цена в рублях
    stock: Mapped[int] = mapped_column(default=0)  # остаток, шт.
    location: Mapped[str] = mapped_column(String(120), default="")  # где лежит (стеллаж/зона)
    description: Mapped[str] = mapped_column(Text, default="")  # характеристики
    # Синонимы/народные названия через запятую — расширяют покрытие поиска.
    aliases: Mapped[str] = mapped_column(Text, default="")
