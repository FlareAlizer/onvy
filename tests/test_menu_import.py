"""Разбор CSV меню и конвертация цены — чистая логика, без БД.

Реальность, под которую эти тесты пишутся: выгрузка меню из Excel под русской
Windows приходит в CP1251 с разделителем ";" — это не гипотетический случай,
управляющий чайханы будет присылать файл именно так (см. задание лупа).
Дубликаты имён внутри файла и сопоставление с БД (create/update) требуют
реальной сессии — см. тесты needs_db в tests/test_menu_api.py.
"""

from decimal import Decimal

import pytest

from app.services.menu import (
    MenuImportError,
    decode_menu_csv,
    parse_menu_csv,
    price_to_decimal,
    price_to_kopecks,
)

# --- Конвертация цены: копейки в БД <-> рубли в порте/API ---------------------


def test_price_to_decimal_converts_kopecks_to_rubles():
    assert price_to_decimal(45000) == Decimal("450.00")


def test_price_to_decimal_keeps_cents():
    assert price_to_decimal(45050) == Decimal("450.50")


def test_price_to_kopecks_roundtrip():
    assert price_to_kopecks(Decimal("450.50")) == 45050
    assert price_to_kopecks(price_to_decimal(45050)) == 45050


def test_price_to_kopecks_rounds_half_up():
    # 450.005 округляется до 45001, а не до 45000 (банковское округление не нужно —
    # цена не бухгалтерский остаток, см. докстринг price_to_kopecks).
    assert price_to_kopecks(Decimal("450.005")) == 45001


def test_price_conversion_never_uses_float():
    """Регрессия на классическую ловушку 0.1 + 0.2: только Decimal на этом пути."""
    price = Decimal("19.99")
    assert price_to_kopecks(price) == 1999
    assert price_to_decimal(1999) == price


# --- Кодировка: реальный случай Excel/Windows-RU (CP1251, разделитель ";") ----


def test_decode_menu_csv_prefers_utf8():
    raw = "название;цена\nЛагман;450\n".encode()
    assert "Лагман" in decode_menu_csv(raw)


def test_decode_menu_csv_falls_back_to_cp1251():
    raw = "название;цена\nЛагман;450\n".encode("cp1251")
    assert "Лагман" in decode_menu_csv(raw)


def test_decode_menu_csv_unreadable_bytes_raise():
    # 0x98 не определён в CP1251 и одновременно невалиден как старт UTF-8-последовательности —
    # единственный байт, гарантированно проваливающий оба кодека (проверено на всех 256 байтах).
    with pytest.raises(MenuImportError):
        decode_menu_csv(b"\x98")


# --- Разбор CSV: cp1251 + ";" — типичный экспорт из Excel под русской Windows -


def _cp1251_csv(*rows: str) -> bytes:
    header = "название;категория;цена;состав;аллергены;вес;время отдачи;острота"
    return "\n".join([header, *rows]).encode("cp1251")


def test_parse_cp1251_semicolon_csv():
    raw = _cp1251_csv("Лагман;Горячее;450;лапша, говядина;глютен;350;15;2")

    rows = parse_menu_csv(raw)

    assert len(rows) == 1
    row = rows[0]
    assert row.is_valid
    assert row.name == "Лагман"
    assert row.category == "Горячее"
    assert row.price == Decimal("450")
    assert row.composition == "лапша, говядина"
    assert row.allergens == ("глютен",)
    assert row.weight_grams == 350
    assert row.prep_time_minutes == 15
    assert row.spiciness == 2


def test_parse_utf8_comma_csv_also_works():
    header = "название,категория,цена,состав,аллергены,вес,время отдачи,острота"
    raw = (header + "\nПлов,Горячее,520,рис; баранина,,400,20,1\n").encode("utf-8")

    rows = parse_menu_csv(raw)

    assert len(rows) == 1
    assert rows[0].name == "Плов"
    assert rows[0].price == Decimal("520")


# --- Различие "пустая ячейка" vs "данных нет" vs "явно проверено" -------------


def test_empty_technical_card_cells_mean_unknown_not_empty():
    """Пустая ячейка состава/аллергенов/веса — None (данных нет), а не пусто.
    Юридически значимо для аллергенов (spec §5 S2): ассистент обязан сказать
    "уточните на кухне", а не промолчать и не додумать."""
    raw = _cp1251_csv("Чай зелёный;Напитки;120;;;;;")

    row = parse_menu_csv(raw)[0]

    assert row.is_valid
    assert row.composition is None
    assert row.allergens is None
    assert row.weight_grams is None
    assert row.prep_time_minutes is None
    assert row.spiciness is None


def test_explicit_no_allergens_word_means_confirmed_empty():
    """Явное слово "нет" в ячейке аллергенов — подтверждённый факт (allergens=()),
    а НЕ то же самое, что пустая ячейка (allergens=None, "не проверялось")."""
    raw = _cp1251_csv("Самса с бараниной;Выпечка;180;тесто, баранина;нет;150;20;1")

    row = parse_menu_csv(raw)[0]

    assert row.allergens == ()
    assert row.allergens is not None


def test_no_allergens_word_is_case_and_space_insensitive():
    raw = _cp1251_csv("Самса;Выпечка;180;тесто;  НЕТ  ;150;20;1")

    row = parse_menu_csv(raw)[0]

    assert row.allergens == ()


def test_allergens_list_parses_multiple_comma_separated_values():
    raw = _cp1251_csv("Плов;Горячее;520;рис, баранина;орехи, молоко;400;20;1")

    row = parse_menu_csv(raw)[0]

    assert row.allergens == ("орехи", "молоко")


# --- Ошибки на уровне строки: отсутствие обязательных полей ------------------


def test_missing_name_is_a_row_error_not_a_crash():
    raw = _cp1251_csv(";Горячее;450;;;;;")

    row = parse_menu_csv(raw)[0]

    assert not row.is_valid
    assert any("название" in e for e in row.errors)


def test_missing_price_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;;;;;;")

    row = parse_menu_csv(raw)[0]

    assert not row.is_valid
    assert any("цена" in e for e in row.errors)


def test_unparseable_price_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;дорого;;;;;")

    row = parse_menu_csv(raw)[0]

    assert not row.is_valid
    assert any("цену" in e for e in row.errors)


def test_negative_price_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;-10;;;;;")

    row = parse_menu_csv(raw)[0]

    assert not row.is_valid


def test_price_with_comma_decimal_separator_is_accepted():
    """Управляющий может ввести цену как в русской локали Excel: "450,50"."""
    raw = _cp1251_csv("Лагман;Горячее;450,50;;;;;")

    row = parse_menu_csv(raw)[0]

    assert row.is_valid
    assert row.price == Decimal("450.50")


def test_spiciness_out_of_range_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;450;;;;;9")

    row = parse_menu_csv(raw)[0]

    assert not row.is_valid
    assert any("острота" in e for e in row.errors)


def test_empty_rows_are_silently_skipped():
    raw = _cp1251_csv("Лагман;Горячее;450;;;;;", ";;;;;;;", "Плов;Горячее;520;;;;;")

    rows = parse_menu_csv(raw)

    assert [r.name for r in rows] == ["Лагман", "Плов"]


def test_missing_required_columns_raises_import_error():
    raw = "категория;состав\nГорячее;лапша\n".encode()

    with pytest.raises(MenuImportError):
        parse_menu_csv(raw)


def test_empty_file_raises_import_error():
    with pytest.raises(MenuImportError):
        parse_menu_csv(b"")


def test_column_order_in_file_does_not_matter():
    """Заголовок ищется по имени колонки, а не по позиции — реальные выгрузки
    из разных касс/Excel не гарантируют один и тот же порядок столбцов."""
    raw = "цена;название;острота\n450;Лагман;2\n".encode()

    row = parse_menu_csv(raw)[0]

    assert row.name == "Лагман"
    assert row.price == Decimal("450")
    assert row.spiciness == 2
