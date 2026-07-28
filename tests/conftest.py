"""Общая настройка тестов.

Окружение выставляется до импорта app.config — Settings читает переменные на импорте
и осознанно падает на неполном конфиге. Тяжёлые импорты (приложение, база) вынесены
внутрь фикстур: пока идёт переезд на новую схему, поломка одного слоя не должна
ронять сбор всех тестов подряд и прятать зелёное за красным.
"""

import os

os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-not-for-production")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://onvy:onvy@localhost:5432/onvy_test")
# Тесты не ходят в реальный Yandex: кому нужен — включает через monkeypatch.
os.environ["YANDEX_API_KEY"] = ""
os.environ["YANDEX_FOLDER_ID"] = ""
