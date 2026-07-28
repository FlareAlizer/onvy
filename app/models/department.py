from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Department(Base):
    """Отдел магазина — группа сотрудников, объединённых на одну смену/связь.

    На демо жюри подключается по QR в один отдел, менеджер вещает всему отделу
    или конкретному сотруднику.
    """

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Демо-отдел")
