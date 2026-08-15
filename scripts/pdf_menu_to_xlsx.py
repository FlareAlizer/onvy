"""Учебное пособие в PDF -> таблица меню для загрузки в Onvy.

Заведения ведут меню не в Excel, а в «учебном пособии» — многостраничном PDF,
где каждая позиция это блок: строка с названием, затем строка с метаданными
(«Время приготовления: 17-22 мин Выход: 250 гр Цена: 990 р») и колонки состава,
описания и подачи. Сетка таблицы от страницы к странице плавает (6, 8, 11
колонок), а метаданные иногда разваливаются на несколько однокле́точных строк —
поэтому разбор идёт не по номерам колонок, а по содержимому ячеек.

Аллергены НЕ выводятся никогда. В пособии их нет, а пустая ячейка в нашем
импорте значит «не проверялись» — ассистент честно отправит официанта уточнить
на кухне. Догадка здесь юридически недопустима (см. docs/menu-upload.md).

Запуск:
    python scripts/pdf_menu_to_xlsx.py "пособие.pdf" -o меню.xlsx --category-prefix "Лето"
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from openpyxl import Workbook

# Строка метаданных позиции. Ключи ищем по отдельности: порядок и наличие
# плавают («Выход: 120/200/5», «Цена: 1 200 ₽», иногда времени нет вовсе).
_ЦЕНА = re.compile(r"Цена\s*:?\s*([\d\s  ]+(?:[.,]\d+)?)")
_ВЫХОД = re.compile(r"Выход\s*:?\s*(\d+)")
_ВРЕМЯ = re.compile(r"Время\s+приготовления\s*:?\s*(\d+)\s*(?:[-–—]\s*(\d+))?")
_МЕТА_КЛЮЧИ = ("Время приготовления", "Выход", "Цена")

# Ячейка сервировки: посуда и приборы. Её ни в коем случае нельзя принять за
# состав — иначе ассистент будет искать аллергены в названии тарелки.
_ПОСУДА = (
    "тарелк", "дублер", "дублёр", "столовые приборы", "салатник", "сковород",
    "блюдо", "подстановочн", "перчатки", "фингербол", "доска", "колба",
    "менажниц", "пиала", "казан", "подача:",
)
_СОСТАВ_МАРКЕРЫ = (
    "украшается", "украшение", "подается", "подаётся", "подаются",
    "заправка", "маринад", "мариновка", "начинка",
)
_НУМЕРАЦИЯ = re.compile(r"\d+\s*\.\s*\S")

# Раздел меню — короткая строка капсом («САЛАТЫ», «ГОРЯЧИЕ БЛЮДА»).
_СЛУЖЕБНЫЕ_ЗАГОЛОВКИ = (
    "фото", "красочное описание", "состав", "подача", "аллергены", "допы",
    "доп. информация", "глоссарий", "кухня", "учебное пособие",
)


@dataclass
class Позиция:
    name: str
    category: str = ""
    price: str = ""
    composition: str = ""
    weight: str = ""
    prep_time: str = ""
    _мета_собрана: bool = field(default=False, repr=False)

    @property
    def готова(self) -> bool:
        return bool(self.name and self.price)


def _чисто(cell: str | None) -> str:
    if not cell:
        return ""
    return re.sub(r"[ \t ]+", " ", cell.replace("\n", " ")).strip()


def _это_раздел(text: str) -> bool:
    буквы = [c for c in text if c.isalpha()]
    if not буквы or len(text) > 60 or any(c.isdigit() for c in text):
        return False
    if any(m in text.casefold() for m in _ПОСУДА):
        return False
    return all(c.isupper() for c in буквы)


def _похоже_на_название(text: str) -> bool:
    """Отсеять обрывки. В PDF абзац описания часто разваливается на строки
    таблицы («Обжаренные тигровые», «креветки в сочетании с»), и каждая такая
    строка выглядит как одноклеточная — то есть неотличима от названия по форме.
    Отличают её хвост и содержимое: название не обрывается на запятой, не
    перечисляет посуду и не бывает длиной в предложение."""
    if not text or len(text) > 70:
        return False
    if any(m in text.casefold() for m in _ПОСУДА):
        return False
    if text.endswith((",", ":", ";", "-", "–", "—")):
        return False
    первая = next((c for c in text if c.isalpha()), "")
    return not (первая and первая.islower())


def _служебная(text: str) -> bool:
    низ = text.casefold()
    return any(marker in низ for marker in _СЛУЖЕБНЫЕ_ЗАГОЛОВКИ)


def _похоже_на_мету(text: str) -> bool:
    return any(key in text for key in _МЕТА_КЛЮЧИ)


def _посуда(text: str) -> bool:
    низ = text.casefold()
    return sum(marker in низ for marker in _ПОСУДА) >= 2


def _вес_состава(text: str) -> int:
    """Насколько ячейка похожа на состав, а не на рекламное описание.

    Состав — перечисление («1. Салат Романо 2. Соус Цезарь...») либо блок с
    пометками вида «Украшается:». Описание — связный текст без нумерации.
    """
    if _посуда(text):
        return -100
    низ = text.casefold()
    нумерация = len(_НУМЕРАЦИЯ.findall(text)) * 3
    маркеры = sum(m in низ for m in _СОСТАВ_МАРКЕРЫ) * 3
    # Связный текст — это «красочное описание», а не техкарта: у него запятые и
    # точки там, где у списка ингредиентов их нет.
    проза = text.count(". ") + text.count(", ")
    return нумерация + маркеры - проза


def _применить_мету(поз: Позиция, text: str) -> None:
    if (m := _ЦЕНА.search(text)) and not поз.price:
        поз.price = re.sub(r"[\s  ]", "", m.group(1)).replace(",", ".")
    if (m := _ВЫХОД.search(text)) and not поз.weight:
        поз.weight = m.group(1)
    if (m := _ВРЕМЯ.search(text)) and not поз.prep_time:
        # «17-22 мин» — обещаем верхнюю границу: гость, услышавший 17 и
        # прождавший 22, недоволен; услышавший 22 и получивший за 17 — нет.
        поз.prep_time = m.group(2) or m.group(1)
    поз._мета_собрана = True


def извлечь(pdf_path: Path) -> tuple[list[Позиция], list[str]]:
    """Позиции и список названий, для которых цена так и не встретилась.

    Позиция материализуется не тогда, когда встретилось название, а когда
    найдена цена: только цена достоверно отделяет настоящее блюдо от обрывка
    описания. До этого имя, состав, вес и время копятся в черновике.
    """
    позиции: list[Позиция] = []
    потеряны: list[str] = []
    раздел = ""
    черновик = Позиция(name="")

    def начать(имя: str) -> None:
        nonlocal черновик
        if черновик.name and not черновик.price:
            потеряны.append(f"{черновик.name} [{черновик.category}]")
        черновик = Позиция(name=имя, category=раздел)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw_row in table:
                    ячейки = [c for c in (_чисто(c) for c in raw_row) if c]
                    if not ячейки:
                        continue

                    if len(ячейки) == 1:
                        one = ячейки[0]
                        if _служебная(one):
                            continue
                        if _это_раздел(one):
                            раздел = one.strip(" ·")
                            continue
                        if _похоже_на_мету(one) or re.fullmatch(
                            r"[\d\s /–—-]+(мин|гр|г|р|₽|руб\.?)?", one
                        ):
                            # Мета, развалившаяся на отдельные строки таблицы.
                            _применить_мету(черновик, one)
                            if черновик.готова:
                                позиции.append(черновик)
                                черновик = Позиция(name="", category=раздел)
                        elif _похоже_на_название(one):
                            начать(one)
                        continue

                    мета = [c for c in ячейки if _похоже_на_мету(c)]
                    прочие = [c for c in ячейки if c not in мета]
                    if not черновик.name:
                        # Название пришло не отдельной строкой, а ячейкой в
                        # общей: берём самую короткую правдоподобную.
                        кандидаты = [c for c in прочие if _похоже_на_название(c)]
                        if кандидаты:
                            начать(min(кандидаты, key=len))
                            прочие = [c for c in прочие if c != черновик.name]
                    if прочие and not черновик.composition:
                        лучший = max(прочие, key=_вес_состава)
                        # Порог только на посуду: пустой состав хуже неидеального.
                        # Без него ассистент отвечает «данных нет» там, где
                        # ингредиенты в пособии есть, просто списком без пометок.
                        if _вес_состава(лучший) > -100:
                            черновик.composition = лучший
                    for c in мета:
                        _применить_мету(черновик, c)

                    if черновик.готова:
                        позиции.append(черновик)
                        черновик = Позиция(name="", category=раздел)

    if черновик.name and not черновик.price:
        потеряны.append(f"{черновик.name} [{черновик.category}]")
    return позиции, потеряны


_ЗАГОЛОВКИ = ["Название", "Категория", "Цена", "Состав", "Аллергены", "Вес", "Время отдачи"]


def записать(позиции: list[Позиция], out: Path, prefix: str = "") -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Меню"
    ws.append(_ЗАГОЛОВКИ)
    for поз in позиции:
        раздел = f"{prefix} · {поз.category}" if prefix and поз.category else (
            prefix or поз.category
        )
        # Аллергены оставляем пустыми осознанно: в пособии их нет, а пустая
        # ячейка означает «не проверялись» — ассистент отправит уточнить.
        ws.append(
            [поз.name, раздел, поз.price, поз.composition, "", поз.weight, поз.prep_time]
        )
    for column, width in zip("ABCDEFG", (42, 26, 10, 70, 18, 8, 14), strict=True):
        ws.column_dimensions[column].width = width
    wb.save(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf")
    parser.add_argument("-o", "--out", required=True)
    parser.add_argument(
        "--category-prefix",
        default="",
        help="приставка к разделу — чтобы летнее меню не слилось с основным",
    )
    args = parser.parse_args()

    позиции, потеряны = извлечь(Path(args.pdf))
    записать(позиции, Path(args.out), args.category_prefix)

    print(f"позиций с названием и ценой: {len(позиции)}  -> {args.out}")
    разделы: dict[str, int] = {}
    for p in позиции:
        разделы[p.category] = разделы.get(p.category, 0) + 1
    for раздел, сколько in разделы.items():
        print(f"    {раздел or '(без раздела)'}: {сколько}")

    без_состава = [p for p in позиции if not p.composition]
    print(f"\nбез состава: {len(без_состава)}")
    for p in без_состава[:20]:
        print(f"    — {p.name}  [{p.category}]")

    print(f"\nбез цены, в файл не попали: {len(потеряны)}")
    for имя in потеряны[:40]:
        print(f"    — {имя}")


if __name__ == "__main__":
    main()
