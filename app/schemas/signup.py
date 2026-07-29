"""Схемы регистрации заведения.

Регистрируется только управляющий и только вместе с новым заведением: он его
владелец с первой минуты. Сотрудников в существующую точку добавляет он сам —
самостоятельная регистрация в чужое заведение открыла бы вход постороннему,
знающему название.
"""

from pydantic import BaseModel, EmailStr, Field

from app.domain.language import Language


class VenueSignupRequest(BaseModel):
    """Регистрация управляющего вместе с его заведением."""

    venue_name: str = Field(min_length=2, max_length=120, description="Название заведения")
    manager_name: str = Field(min_length=2, max_length=120, description="Имя управляющего")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str = Field(default="Europe/Moscow", max_length=64)
    default_language: Language = "ru"


class VenueSignupResult(BaseModel):
    """Что получилось: заведение, кабинет и сразу пара токенов.

    Токены отдаются здесь же, чтобы человек не вводил пароль второй раз сразу
    после регистрации.
    """

    venue_id: int
    venue_name: str
    employee_id: int
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
