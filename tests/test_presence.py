"""Шина связи и присутствие на смене.

Тесты появились после того, как развёрнутый сервер сутки писал бы в лог
«шина связи недоступна» раз в секунду: читатель дёргал pubsub до того, как
кто-либо подписался. Ошибкой это не было — просто на смену ещё никто не вышел.
"""

import asyncio

import fakeredis.aioredis
import pytest

from app.services.presence import CommsBus, ConnectionRegistry, Presence


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


class TestШина:
    async def test_читатель_молчит_пока_никто_не_подключён(self, redis, caplog):
        """Пустой процесс без сотрудников не должен спамить в лог."""
        bus = CommsBus(redis, ConnectionRegistry())
        await bus.start()
        await asyncio.sleep(0.3)
        await bus.stop()

        assert "недоступна" not in caplog.text

    async def test_сообщение_доходит_до_подключённого_сокета(self, redis):
        registry = ConnectionRegistry()
        доставлено: list[dict] = []

        class Сокет:
            async def send_json(self, payload):
                доставлено.append(payload)

        registry.add(7, Сокет())  # type: ignore[arg-type]
        bus = CommsBus(redis, registry)
        await bus.start()
        await bus.attach(7)

        await bus.publish(7, {"text": "стол пять готов"})
        for _ in range(20):
            if доставлено:
                break
            await asyncio.sleep(0.05)
        await bus.stop()

        assert доставлено == [{"text": "стол пять готов"}]

    async def test_переподключение_не_гасит_новый_сокет(self, redis):
        """Регрессия: закрытие старого сокета выбрасывало из реестра живой.

        На плохом вайфае телефон переподключается раньше, чем сервер узнаёт о
        разрыве прошлого соединения. Безусловный remove снимал свежий сокет, а
        вызывающий следом отписывал его от шины и снимал сотрудника со смены.
        Наружу это выглядело так: человек числится «на смене» — пинг нового
        сокета обновляет отметку, — а реплики до него молча не доходят.
        """
        registry = ConnectionRegistry()
        доставлено: list[dict] = []

        class Сокет:
            def __init__(self, метка: str) -> None:
                self.метка = метка

            async def send_json(self, payload):
                доставлено.append({**payload, "кому": self.метка})

        старый, новый = Сокет("старый"), Сокет("новый")
        registry.add(7, старый)  # type: ignore[arg-type]
        registry.add(7, новый)  # type: ignore[arg-type]

        # Старое соединение закрывается уже после того, как открылось новое.
        снят = registry.remove(7, старый)  # type: ignore[arg-type]

        assert снят is False, "старый сокет не должен считаться текущим"
        assert registry.has(7), "живой сокет обязан остаться в реестре"
        assert await registry.send(7, {"text": "стол пять готов"})
        assert доставлено == [{"text": "стол пять готов", "кому": "новый"}]

    async def test_свой_сокет_снимается(self, redis):
        """Обратная сторона: закрылось текущее соединение — сотрудник ушёл."""
        registry = ConnectionRegistry()

        class Сокет:
            async def send_json(self, payload):
                pass

        сокет = Сокет()
        registry.add(7, сокет)  # type: ignore[arg-type]

        assert registry.remove(7, сокет) is True  # type: ignore[arg-type]
        assert not registry.has(7)

    async def test_отписка_прекращает_доставку(self, redis):
        registry = ConnectionRegistry()
        bus = CommsBus(redis, registry)
        await bus.start()
        await bus.attach(7)
        await bus.detach(7)
        await asyncio.sleep(0.1)
        await bus.stop()
        # Главное — что отписка и последующая остановка не падают.


class TestПрисутствие:
    async def test_отметился_значит_на_смене(self, redis):
        presence = Presence(redis)
        await presence.touch(venue_id=1, employee_id=42)

        assert await presence.online(1) == {42}

    async def test_ушёл_со_смены(self, redis):
        presence = Presence(redis)
        await presence.touch(venue_id=1, employee_id=42)
        await presence.leave(venue_id=1, employee_id=42)

        assert await presence.online(1) == set()

    async def test_протухшая_отметка_выпадает_сама(self, redis, monkeypatch):
        """Телефон уснул в кармане — сотрудник перестаёт числиться на смене."""
        import app.services.presence as модуль

        presence = Presence(redis)
        await presence.touch(venue_id=1, employee_id=42)

        # Перематываем часы вперёд за срок жизни отметки.
        позже = модуль.time.time() + модуль.ONLINE_TTL_SECONDS + 1
        monkeypatch.setattr(модуль.time, "time", lambda: позже)

        assert await presence.online(1) == set()

    async def test_точки_не_видят_друг_друга(self, redis):
        presence = Presence(redis)
        await presence.touch(venue_id=1, employee_id=1)
        await presence.touch(venue_id=2, employee_id=2)

        assert await presence.online(1) == {1}
        assert await presence.online(2) == {2}


class TestПереподключениеНаДругуюРеплику:
    """Реестр сокетов локален для процесса, присутствие — общее на все реплики.

    Регрессия: телефон переподключался на соседнюю реплику, старый процесс видел
    закрытие СВОЕГО сокета как закрытие текущего соединения и снимал человека со
    смены. Наружу — худший из возможных видов отказа: телефон на связи, пинги
    идут, а реплики не доходят, потому что в списке онлайна человека нет.
    """

    async def test_старое_соединение_не_снимает_переподключившегося(self, redis):
        presence = Presence(redis)

        # Реплика A: сотрудник вышел на смену.
        await presence.join(venue_id=1, employee_id=42, connection_id="реплика-A")
        # Реплика B: тот же телефон переподключился, пока A ещё не знает о разрыве.
        await presence.join(venue_id=1, employee_id=42, connection_id="реплика-B")

        # И только теперь до A доходит закрытие её сокета.
        снят = await presence.leave(
            venue_id=1, employee_id=42, connection_id="реплика-A"
        )

        assert снят is False, "чужое соединение не снимает со смены"
        assert await presence.online(1) == {42}, "живой телефон обязан остаться на смене"

    async def test_владелец_текущего_соединения_снимается(self, redis):
        """Обратная сторона: ушёл тот, кто держал смену, — и смена закрыта."""
        presence = Presence(redis)
        await presence.join(venue_id=1, employee_id=42, connection_id="реплика-B")

        снят = await presence.leave(
            venue_id=1, employee_id=42, connection_id="реплика-B"
        )

        assert снят is True
        assert await presence.online(1) == set()

    async def test_пинг_старого_сокета_не_перехватывает_смену(self, redis):
        """Старый сокет ещё жив и шлёт пинг: продлить присутствие он вправе,
        а вот забрать соединение себе — нет, иначе уход нового снова разъедется
        с реальностью."""
        presence = Presence(redis)
        await presence.join(venue_id=1, employee_id=42, connection_id="реплика-A")
        await presence.join(venue_id=1, employee_id=42, connection_id="реплика-B")

        await presence.touch(venue_id=1, employee_id=42)  # пинг от старого сокета

        assert await presence.leave(1, 42, "реплика-A") is False
        assert await presence.leave(1, 42, "реплика-B") is True
