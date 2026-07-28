"""Контекст меню для ассистента.

Проверяем не «красиво собралось», а то, ради чего он такой: незаполненные поля
должны доезжать до модели как явное «НЕ ЗАПОЛНЕНО», иначе модель примет пропуск
за разрешение придумать состав блюда. Про аллергены это вопрос ответственности
заведения перед гостем, а не качества ответа.
"""

from decimal import Decimal

from app.adapters.yandex.answer import build_menu_context
from app.ports.menu import MenuItemData

ЛАГМАН = MenuItemData(
    external_id="lagman",
    name="Лагман",
    category="Горячее",
    price=Decimal("450"),
    composition="лапша, говядина, болгарский перец",
    allergens=("глютен",),
    spiciness=1,
    weight_grams=350,
    prep_time_minutes=15,
)


def test_незаполненные_аллергены_помечаются_явным_запретом():
    item = MenuItemData(
        external_id="plov", name="Плов", category=None, price=None, allergens=None
    )

    context = build_menu_context([item], stopped=frozenset())

    assert "аллергены: НЕ ЗАПОЛНЕНЫ" in context
    assert "отвечать нельзя" in context


def test_проверенное_отсутствие_аллергенов_отличается_от_незаполненного():
    """Пустой кортеж — это «повар проверил, аллергенов нет», а не «данных нет»."""
    item = MenuItemData(
        external_id="tea", name="Чай", category="Напитки", price=None, allergens=()
    )

    context = build_menu_context([item], stopped=frozenset())

    assert "аллергены: проверено, нет" in context
    assert "НЕ ЗАПОЛНЕНЫ" not in context


def test_незаполненный_состав_помечается():
    item = MenuItemData(external_id="samsa", name="Самса", category=None, price=None)

    context = build_menu_context([item], stopped=frozenset())

    assert "состав: НЕ ЗАПОЛНЕН" in context


def test_стоп_лист_виден_в_карточке():
    context = build_menu_context([ЛАГМАН], stopped=frozenset({"lagman"}))

    assert "СТОП-ЛИСТЕ" in context
    assert "продавать нельзя" in context


def test_заполненная_карточка_отдаёт_все_факты():
    context = build_menu_context([ЛАГМАН], stopped=frozenset())

    assert "Лагман" in context
    assert "450" in context
    assert "глютен" in context
    assert "выход 350 г" in context
    assert "готовится 15 мин" in context
    assert "НЕ ЗАПОЛНЕН" not in context


def test_пустое_меню_не_притворяется_найденным():
    context = build_menu_context([], stopped=frozenset())

    assert "не найдено" in context
