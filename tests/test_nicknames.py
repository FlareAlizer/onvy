"""Проверка кличек — то, чем сотрудников окликают голосом.

Каждый случай здесь — реальный способ сломать адресацию тихо: пилот запустится,
а обращения будут уезжать не туда, и разбираться придётся в разгар смены.
"""

from app.domain.nicknames import check_nicknames

МЕНЮ = ["Плов по-фергански", "Лагман", "Самса с бараниной", "Чай зелёный"]


def сообщения(problems) -> str:
    return " | ".join(str(p) for p in problems)


class TestХорошиеКлички:
    def test_обычный_набор_проходит(self):
        assert check_nicknames(["Азиз", "Малика", "Шеф", "Дилшод"], menu_names=МЕНЮ) == []

    def test_пустые_и_отсутствующие_пропускаются(self):
        """Кличка необязательна — тогда обращение ищут по первому слову имени."""
        assert check_nicknames([None, "", "   ", "Азиз"]) == []


class TestДвойники:
    def test_точный_дубль(self):
        problems = check_nicknames(["Азиз", "Азиз"])

        assert len(problems) == 1
        assert "не поймёт, кого из двоих" in сообщения(problems)

    def test_дубль_в_другом_регистре(self):
        assert len(check_nicknames(["Азиз", "АЗИЗ"])) == 1

    def test_неотличимые_на_слух(self):
        """«Малика» и «Малина» распознавание путает — это тот же конфликт."""
        problems = check_nicknames(["Малика", "Малина"])

        assert len(problems) == 1


class TestСлужебныеСлова:
    def test_кличка_совпадающая_с_отделом(self):
        problems = check_nicknames(["Бар"])

        assert "служебным словом" in сообщения(problems)

    def test_кличка_в_падеже_от_отдела(self):
        assert check_nicknames(["Кухня"]) != []

    def test_кличка_похожая_на_имя_ассистента(self):
        assert check_nicknames(["Онви"]) != []


class TestКонфликтСМеню:
    def test_кличка_совпадает_с_блюдом(self):
        problems = check_nicknames(["Плов"], menu_names=МЕНЮ)

        assert "из меню" in сообщения(problems)

    def test_кличка_совпадает_со_словом_внутри_названия(self):
        """«Самса с бараниной» — «Самса» отдельным словом тоже занята."""
        assert check_nicknames(["Самса"], menu_names=МЕНЮ) != []

    def test_без_меню_проверка_не_срабатывает(self):
        assert check_nicknames(["Плов"]) == []


class TestФормат:
    def test_слишком_короткая(self):
        problems = check_nicknames(["Ян"])

        assert "слишком короткая" in сообщения(problems)

    def test_из_нескольких_слов(self):
        problems = check_nicknames(["Дядя Ваня"])

        assert "одним словом" in сообщения(problems)


def test_проблемы_собираются_по_всем_сотрудникам():
    problems = check_nicknames(["Азиз", "Бар", "Плов", "Азиз"], menu_names=МЕНЮ)

    assert len(problems) == 3
