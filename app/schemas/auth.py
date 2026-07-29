"""Схемы запросов/ответов входа, обновления токена и WS-тикета.

Никаких внутренностей наружу: клиент не должен по форме ответа отличать
«сотрудника не существует» от «сотрудник существует, PIN неверный» —
см. app/services/auth.py и app/api/auth.py.
"""

from pydantic import BaseModel, EmailStr, Field


class EmployeeLoginOption(BaseModel):
    """Один пункт списка «выбери себя» на экране входа точки.

    Только то, что безопасно показать до аутентификации — никакого pin_hash.
    """

    id: int
    name: str
    role: str
    language: str

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    """Тело POST /api/auth/login: сотрудник выбран из списка своей точки."""

    employee_id: int
    pin: str = Field(min_length=4, max_length=12)


class EmailLoginRequest(BaseModel):
    """Тело POST /api/auth/login-email — основной способ входа.

    Пароль ограничен снизу восемью символами, сверху — 128: длинную парольную
    фразу пускаем, но не даём положить сервер гигабайтом на argon2.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class MeOut(BaseModel):
    """Кто вошёл — клиент рисует по этому кабинет и подставляет имя."""

    id: int
    venue_id: int
    venue_name: str
    name: str
    nickname: str | None
    email: str | None
    role: str
    language: str


class RefreshRequest(BaseModel):
    """Тело POST /api/auth/refresh."""

    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    """Ответ на успешный вход/обновление токена."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Время жизни access-токена, секунды")


class WsTicketOut(BaseModel):
    """Ответ на POST /api/auth/ws-ticket: одноразовый тикет для WS-подключения."""

    ticket: str
    expires_in: int = Field(description="Время жизни тикета, секунды")
