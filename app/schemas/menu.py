"""Схемы запросов/ответов меню и стоп-листа (кабинет управляющего).

Техкарта (composition/allergens/spiciness/weight_grams/prep_time_minutes) —
опциональна везде: см. app/ports/menu.py и app/db/models/menu_item.py. Для
MenuItemPatch это осознанно: поле отсутствует в теле запроса — не трогаем
текущее значение; поле передано как null — явный сброс в "данных нет"
(допустимо для техкарты, запрещено для name/price — их валидность проверяет
app/api/menu.py через model_fields_set перед вызовом сервиса).
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MenuItemIn(BaseModel):
    """Тело POST при создании позиции."""

    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=120)
    price: Decimal = Field(ge=0, description="Цена в рублях, напр. 450.00")
    composition: str | None = None
    allergens: list[str] | None = Field(
        default=None, description="null — не проверялись, [] — кухня подтвердила: аллергенов нет"
    )
    spiciness: int | None = Field(default=None, ge=0, le=3)
    weight_grams: int | None = Field(default=None, ge=0)
    prep_time_minutes: int | None = Field(default=None, ge=0)


class MenuItemPatch(BaseModel):
    """Тело PATCH при редактировании позиции. Все поля опциональны — см. докстринг модуля."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=120)
    price: Decimal | None = Field(default=None, ge=0)
    composition: str | None = None
    allergens: list[str] | None = None
    spiciness: int | None = Field(default=None, ge=0, le=3)
    weight_grams: int | None = Field(default=None, ge=0)
    prep_time_minutes: int | None = Field(default=None, ge=0)


class MenuItemOut(BaseModel):
    """Позиция меню в ответе API — цена уже в рублях, а не в копейках БД."""

    id: int
    name: str
    category: str | None
    price: Decimal
    composition: str | None
    allergens: list[str] | None
    spiciness: int | None
    weight_grams: int | None
    prep_time_minutes: int | None


# --- Импорт CSV ---------------------------------------------------------------


class MenuImportRowOut(BaseModel):
    """Одна строка файла после разбора — и для превью, и для отчёта о применении."""

    line_number: int
    name: str
    category: str | None
    price: Decimal | None
    composition: str | None
    allergens: list[str] | None
    spiciness: int | None
    weight_grams: int | None
    prep_time_minutes: int | None
    errors: list[str] = Field(default_factory=list)


class MenuImportUpdateRowOut(BaseModel):
    """Строка на обновление — вместе с id позиции, которую она затронет."""

    row: MenuImportRowOut
    menu_item_id: int


class MenuImportPreviewOut(BaseModel):
    """Ответ на импорт CSV. applied=False значит dry-run: ничего не записано в БД,
    управляющий видит план ДО применения (это требование, не деталь UX)."""

    to_create: list[MenuImportRowOut]
    to_update: list[MenuImportUpdateRowOut]
    rejected: list[MenuImportRowOut]
    applied: bool


# --- Стоп-лист ------------------------------------------------------------------


class StopListActionIn(BaseModel):
    """Тело POST при постановке в стоп. Причина не обязательна — S4 требует, чтобы
    действие занимало секунды: одно нажатие без формы должно работать."""

    reason: str | None = Field(default=None, max_length=300)


class StopListEntryOut(BaseModel):
    id: int
    menu_item_id: int
    menu_item_name: str
    set_at: datetime
    unset_at: datetime | None
    set_by_employee_id: int
    unset_by_employee_id: int | None
    reason: str | None
