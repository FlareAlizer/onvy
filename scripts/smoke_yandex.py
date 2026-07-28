"""Живая проверка речевого стека Yandex — запусти ПОСЛЕ заполнения .env.

    uv run python scripts/smoke_yandex.py

Проверяет по очереди TTS → STT → Translate реальными вызовами (тратит копейки).
Если всё зелёное — голосовой MVP готов к демо на наушниках.
"""

import asyncio
import sys
from pathlib import Path

# Консоль Windows (cp1251) не печатает эмодзи — форсируем UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Чтобы `app` импортировался при запуске из папки scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.services import llm, speech  # noqa: E402
from app.services.translation import YandexTranslator  # noqa: E402


async def main() -> int:
    if not settings.yandex_enabled:
        print("❌ YANDEX_API_KEY / YANDEX_FOLDER_ID не заданы в .env")
        return 1

    print("1/4 TTS: синтезирую фразу…")
    audio = await speech.synthesize(
        "Проверка связи Onvy. Наушники Sony, тридцать четыре тысячи.", "ru"
    )
    print(f"    ✓ получено {len(audio)} байт MP3")

    print("2/4 STT: распознаю синтезированное аудио…")
    # TTS вернул MP3, а STT ждёт LPCM — для честной проверки STT нужен реальный
    # PCM с микрофона. Здесь проверяем только, что запрос проходит без ошибок сети.
    try:
        text = await speech.recognize(b"\x00\x00" * 16000, "ru")  # 1 сек тишины (LPCM)
        print(f"    ✓ STT ответил (текст: {text!r}; на тишине пусто — это норма)")
    except speech.SpeechError as exc:
        print(f"    ❌ STT ошибка: {exc}")
        return 1

    print("3/4 Translate: RU → EN…")
    result = await YandexTranslator().translate("Подойди на кассу", "ru", "en")
    print(f"    ✓ перевод: {result.text!r} (provider={result.provider})")

    print("4/4 YandexGPT: вопрос по мини-каталогу…")
    demo = [Product(name="Наушники Sony", price=34990, stock=4, location="стеллаж A3")]
    answer = await llm.answer_over_catalog("Где лежат наушники и сколько их?", demo, "ru")
    print(f"    ✓ ответ ассистента: {answer!r}")

    print("\n✅ Речевой стек + LLM Yandex работают. Можно тестировать /rop и /worker.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
