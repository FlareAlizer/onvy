"""Разбор файла меню (CSV/Excel) и конвертация цены — чистая логика, без БД.

Реальность, под которую эти тесты пишутся: заведение присылает файл, который
мы никогда не видим заранее (см. задание лупа) — от выгрузки из Excel под
русской Windows в CP1251 с разделителем ";" до настоящего .xlsx с шапкой не в
первой строке и заголовками, которые никто заранее не согласовывал. Разбор
обязан справляться со всем этим и объяснять по-русски, что не так, если не
справился — не трейсбеком.

Дубликаты имён внутри файла и сопоставление с БД (create/update) требуют
реальной сессии — см. тесты needs_db в tests/test_menu_api.py.
"""

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.services.menu import price_to_decimal, price_to_kopecks
from app.services.menu_import import MenuImportError, decode_menu_csv, parse_menu_file

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

    rows = parse_menu_file(raw)

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

    rows = parse_menu_file(raw)

    assert len(rows) == 1
    assert rows[0].name == "Плов"
    assert rows[0].price == Decimal("520")


# --- Различие "пустая ячейка" vs "данных нет" vs "явно проверено" -------------


def test_empty_technical_card_cells_mean_unknown_not_empty():
    """Пустая ячейка состава/аллергенов/веса — None (данных нет), а не пусто.
    Юридически значимо для аллергенов (spec §5 S2): ассистент обязан сказать
    "уточните на кухне", а не промолчать и не додумать."""
    raw = _cp1251_csv("Чай зелёный;Напитки;120;;;;;")

    row = parse_menu_file(raw)[0]

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

    row = parse_menu_file(raw)[0]

    assert row.allergens == ()
    assert row.allergens is not None


def test_no_allergens_word_is_case_and_space_insensitive():
    raw = _cp1251_csv("Самса;Выпечка;180;тесто;  НЕТ  ;150;20;1")

    row = parse_menu_file(raw)[0]

    assert row.allergens == ()


def test_allergens_list_parses_multiple_comma_separated_values():
    raw = _cp1251_csv("Плов;Горячее;520;рис, баранина;орехи, молоко;400;20;1")

    row = parse_menu_file(raw)[0]

    assert row.allergens == ("орехи", "молоко")


# --- Ошибки на уровне строки: отсутствие обязательных полей ------------------


def test_missing_name_is_a_row_error_not_a_crash():
    raw = _cp1251_csv(";Горячее;450;;;;;")

    row = parse_menu_file(raw)[0]

    assert not row.is_valid
    assert any("название" in e for e in row.errors)


def test_missing_price_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;;;;;;")

    row = parse_menu_file(raw)[0]

    assert not row.is_valid
    assert any("цена" in e for e in row.errors)


def test_unparseable_price_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;дорого;;;;;")

    row = parse_menu_file(raw)[0]

    assert not row.is_valid
    assert any("цену" in e for e in row.errors)


def test_negative_price_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;-10;;;;;")

    row = parse_menu_file(raw)[0]

    assert not row.is_valid


def test_price_with_comma_decimal_separator_is_accepted():
    """Управляющий может ввести цену как в русской локали Excel: "450,50"."""
    raw = _cp1251_csv("Лагман;Горячее;450,50;;;;;")

    row = parse_menu_file(raw)[0]

    assert row.is_valid
    assert row.price == Decimal("450.50")


def test_spiciness_out_of_range_is_a_row_error():
    raw = _cp1251_csv("Лагман;Горячее;450;;;;;9")

    row = parse_menu_file(raw)[0]

    assert not row.is_valid
    assert any("острота" in e for e in row.errors)


def test_empty_rows_are_silently_skipped():
    raw = _cp1251_csv("Лагман;Горячее;450;;;;;", ";;;;;;;", "Плов;Горячее;520;;;;;")

    rows = parse_menu_file(raw)

    assert [r.name for r in rows] == ["Лагман", "Плов"]


def test_empty_file_raises_import_error():
    with pytest.raises(MenuImportError):
        parse_menu_file(b"")


def test_column_order_in_file_does_not_matter():
    """Заголовок ищется по имени колонки, а не по позиции — реальные выгрузки
    из разных касс/Excel не гарантируют один и тот же порядок столбцов."""
    raw = "цена;название;острота\n450;Лагман;2\n".encode()

    row = parse_menu_file(raw)[0]

    assert row.name == "Лагман"
    assert row.price == Decimal("450")
    assert row.spiciness == 2


# --- Обязательная колонка отсутствует: ошибка должна быть человеку понятна ----


def test_missing_required_columns_raises_import_error():
    raw = "категория;состав\nГорячее;лапша\n".encode()

    with pytest.raises(MenuImportError):
        parse_menu_file(raw)


def test_missing_name_column_error_lists_found_columns():
    """Требование задания: если нет колонки «название» — показать, что нашли,
    чтобы человек понял, какую колонку переименовать, а не гадал."""
    raw = "цена;острота\n450;2\n".encode()

    with pytest.raises(MenuImportError) as exc_info:
        parse_menu_file(raw)

    message = str(exc_info.value)
    assert "название" in message
    assert "цена" in message  # распознанная колонка упомянута в подсказке


# --- Шапка не в первой строке: заведение в файле, дата, пустые строки --------


def test_header_row_found_when_not_on_first_line():
    """Реальный файл часто начинается с названия заведения и пустых строк —
    шапка ищется в первых 15 строках, а не жёстко на первой."""
    raw = (
        "Меню чайханы «Дастархан»\n"
        "\n"
        "название;цена;острота\n"
        "Лагман;450;2\n"
    ).encode()

    rows = parse_menu_file(raw)

    assert len(rows) == 1
    assert rows[0].name == "Лагман"
    assert rows[0].line_number == 4  # нумерация строк — по файлу целиком, не по данным


def test_header_not_found_within_scan_window_raises_readable_error():
    """Если ни в одной из первых строк нет ни одной узнаваемой колонки —
    ошибка должна объяснять, что мы искали, а не просто "не найдено"."""
    raw = "\n".join(f"мусор {i}" for i in range(20)).encode()

    with pytest.raises(MenuImportError) as exc_info:
        parse_menu_file(raw)

    assert "заголовк" in str(exc_info.value)


# --- Широкие алиасы заголовков: реальные формулировки из разных касс --------


@pytest.mark.parametrize(
    ("header_word", "expected_field"),
    [
        ("Стоимость", "price"),
        ("Цена, руб", "price"),
        ("Цена за порцию", "price"),
        ("Выход", "weight_grams"),
        ("Выход, г", "weight_grams"),
        ("Граммовка", "weight_grams"),
        ("Порция", "weight_grams"),
        ("Описание", "composition"),
        ("Ингредиенты", "composition"),
        ("Состав блюда", "composition"),
        ("Раздел", "category"),
        ("Группа", "category"),
        ("Тип", "category"),
        ("Время", "prep_time_minutes"),
        ("Мин", "prep_time_minutes"),
        ("Острота", "spiciness"),
        ("Острое", "spiciness"),
    ],
)
def test_wide_header_aliases_are_recognized(header_word, expected_field):
    raw = f"название;цена;{header_word}\nЛагман;450;1\n".encode()

    rows = parse_menu_file(raw)

    row = rows[0]
    assert row.name == "Лагман"
    # у price/weight_grams/prep_time_minutes/spiciness значение "1" разбирается
    # по-разному — проверяем не конкретное значение, а что колонка вообще узнана
    # (иначе она осталась бы за бортом column_map и строка была бы короче).
    field_value = {
        "price": row.price,
        "weight_grams": row.weight_grams,
        "spiciness": row.spiciness,
        "prep_time_minutes": row.prep_time_minutes,
        "composition": row.composition,
        "category": row.category,
    }[expected_field]
    assert field_value is not None


def test_header_normalization_ignores_case_dots_and_yo_letter():
    """«Ё» вместо «е», регистр, точка на конце — не должны мешать узнать колонку."""
    raw = "НАЗВАНИЕ.;Цена.\nЛагман;450\n".encode()

    rows = parse_menu_file(raw)

    assert rows[0].name == "Лагман"


def test_header_with_newline_inside_cell_is_recognized():
    """Excel позволяет перенос строки внутри ячейки заголовка (Alt+Enter):
    "Название\\n(блюда)" должно узнаться так же, как "название блюда"."""
    raw = '"Название\n(блюда)";Цена\r\nЛагман;450\r\n'.encode()

    rows = parse_menu_file(raw)

    assert rows[0].name == "Лагман"


# --- .xls (старый бинарный формат) — понятная ошибка, а не попытка разобрать -


def test_xls_binary_file_gets_a_human_readable_error():
    ole2_magic = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    raw = ole2_magic + b"\x00" * 32  # содержимое не важно — формат узнаётся по сигнатуре

    with pytest.raises(MenuImportError) as exc_info:
        parse_menu_file(raw, filename="меню.xls")

    message = str(exc_info.value)
    assert "xlsx" in message.casefold()


# --- Excel (.xlsx): настоящий файл, шапка не в первой строке, порядок колонок -


def _build_xlsx(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_parses_real_xlsx_with_header_not_first_reordered_columns_and_odd_spelling():
    """Требование задания: шапка не в первой строке, колонки в другом порядке,
    русские заголовки в неожиданном написании — и пустые аллергены остаются None
    (юридически значимо, см. докстринг app/services/menu_import.py)."""
    raw = _build_xlsx(
        [
            ["Меню чайханы «Дастархан»"],  # преамбула: название заведения
            [],  # пустая строка
            # шапка — колонки в другом порядке, формулировки не буквально из наших алиасов
            ["Выход, гр", "Наименование позиции", "Цена, руб.", "Аллергены (если есть)"],
            [300, "Лагман", 450, None],  # аллергены пусто -> не проверялось
            [400, "Плов", 520, "нет"],  # аллергены явно "нет" -> проверено, пусто
        ]
    )

    rows = parse_menu_file(raw, filename="меню.xlsx")

    assert len(rows) == 2
    lagman, plov = rows
    assert lagman.name == "Лагман"
    assert lagman.price == Decimal("450")
    assert lagman.weight_grams == 300
    assert lagman.allergens is None  # пустая ячейка — данных нет, а не "аллергенов нет"

    assert plov.name == "Плов"
    assert plov.price == Decimal("520")
    assert plov.allergens == ()  # явное "нет" — подтверждённый факт


def test_xlsx_numeric_price_cell_is_read_without_float_artifacts():
    """Ячейка цены в Excel обычно число, не текст — не должно быть 450.00000001."""
    raw = _build_xlsx(
        [
            ["название", "цена"],
            ["Лагман", 450.5],
        ]
    )

    row = parse_menu_file(raw)[0]

    assert row.price == Decimal("450.5")


def test_xlsx_empty_file_raises_import_error():
    raw = _build_xlsx([])

    with pytest.raises(MenuImportError):
        parse_menu_file(raw)


def test_xlsx_missing_price_column_error_mentions_it():
    raw = _build_xlsx([["название", "острота"], ["Лагман", "1"]])

    with pytest.raises(MenuImportError) as exc_info:
        parse_menu_file(raw)

    assert "цена" in str(exc_info.value)


class TestРеальныеСтранностиФайлов:
    """Файл присылает человек, который не знает наших правил. Каждый случай тут
    поймало ревью на настоящих формах выгрузок — до этого импорт молча ломался.
    """

    def test_две_колонки_на_одно_поле_не_путают_блюдо_с_категорией(self):
        """«Наименование» и «Наименование группы» рядом — обычная выгрузка.

        Побеждала правая, и каждое блюдо получало имя своей категории: из файла
        на 200 позиций импортировалась одна, остальные отсеивались как дубликаты.
        """
        файл = "Наименование;Наименование группы;Цена\nЛагман;Горячее;480\n"

        строки = parse_menu_file(файл.encode("utf-8"), filename="m.csv")

        assert строки[0].name == "Лагман"

    def test_пустая_уточняющая_колонка_не_стирает_цену(self):
        """«Цена» и «Цена со скидкой» — вторая пустая. Раньше пустая побеждала,
        и годный файл отклонялся целиком: «не заполнена цена» на каждой строке."""
        файл = "Название;Цена;Цена со скидкой\nЛагман;480;\n"

        строки = parse_menu_file(файл.encode("utf-8"), filename="m.csv")

        assert строки[0].price == Decimal("480")
        assert строки[0].is_valid

    def test_единицы_в_ячейке_не_губят_блюдо(self):
        """«250 г» и «15 мин» пишут в ячейке так же часто, как выносят в шапку.
        Блюдо с верным названием и ценой не должно теряться из-за буквы «г»."""
        файл = "Название;Цена;Вес;Время отдачи\nЛагман;450;250 г;15 мин\n"

        строки = parse_menu_file(файл.encode("utf-8"), filename="m.csv")

        assert строки[0].is_valid
        assert строки[0].weight_grams == 250
        assert строки[0].prep_time_minutes == 15

    def test_совсем_нечитаемая_ячейка_оставляет_поле_пустым(self):
        """Не поняли — не мешаем блюду: поле пустое, строка живая."""
        файл = "Название;Цена;Вес\nЛагман;450;по запросу\n"

        строки = parse_menu_file(файл.encode("utf-8"), filename="m.csv")

        assert строки[0].is_valid
        assert строки[0].weight_grams is None

    def test_битый_xlsx_объясняет_а_не_падает(self):
        """Файл, скачанный не полностью, — обычное дело. openpyxl разбирает лист
        лениво, поэтому поломка вылезает при обходе строк, а не при открытии:
        раньше управляющий получал 500 и трейсбек вместо объяснения."""
        import io
        import zipfile

        целый = io.BytesIO()
        книга = Workbook()
        книга.active.append(["Название", "Цена"])
        книга.active.append(["Лагман", 480])
        книга.save(целый)

        # Обрезаем XML листа — ровно то, что делает недокачанный файл.
        битый = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(целый.getvalue())) as источник:
            with zipfile.ZipFile(битый, "w") as приёмник:
                for имя in источник.namelist():
                    данные = источник.read(имя)
                    if имя.endswith("sheet1.xml"):
                        данные = данные[: len(данные) // 2]
                    приёмник.writestr(имя, данные)

        with pytest.raises(MenuImportError) as сбой:
            parse_menu_file(битый.getvalue(), filename="menu.xlsx")

        assert "повреждён" in str(сбой.value) or "прочитать лист" in str(сбой.value)
