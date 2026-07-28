"""Конфигурация приложения: только из окружения, проверяется на старте.

Принцип: если конфиг неполный или противоречивый — падаем громко при запуске,
а не через два часа пилота, когда официант нажмёт кнопку. Ни одного секрета
в коде и ни одного «тихого» дефолта для боевых значений.
"""

from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.language import Language

AsrProvider = Literal["yandex", "gigaam"]


class Settings(BaseSettings):
    # --- Среда ---
    env: Literal["dev", "prod"] = "dev"
    debug: bool = False

    # --- Инфраструктура ---
    database_url: str = "postgresql+asyncpg://onvy:onvy@localhost:5432/onvy"
    redis_url: str = "redis://localhost:6379/0"

    # --- Аутентификация ---
    # Ключ подписи JWT. В проде обязан быть длинным и заданным явно.
    secret_key: str
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    # Сколько раз подряд можно ошибиться PIN-ом до временной блокировки входа.
    pin_max_attempts: int = 5
    pin_lockout_minutes: int = 15

    # --- Языки ---
    default_language: Language = "ru"

    # --- Распознавание речи ---
    # Основной провайдер. На старте пилота — yandex (работает сразу), после
    # разворачивания GPU-ноды переключается на gigaam без правок кода.
    asr_provider: AsrProvider = "yandex"
    # Куда ходить за распознаванием на своей ноде (наш HTTP-обёртка над GigaAM).
    gigaam_url: str = ""
    gigaam_timeout_seconds: float = 15.0
    # Языки, которые отдаём GigaAM. Остальные уходят запасному провайдеру:
    # GigaAM-Multilingual покрывает ru/en/kk/ky/uz, таджикского у неё нет.
    gigaam_languages: str = "ru,uz,kk,ky,en"
    # Провайдер для языков, которых нет у основного. Пустая строка — без запасного.
    asr_fallback_provider: AsrProvider | Literal[""] = "yandex"

    # --- Yandex Cloud: ASR, TTS, Translate, GPT ---
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    yandex_gpt_model: str = "yandexgpt-lite"

    # --- Хранение ---
    # Срок жизни сырого аудио. Держим коротким осознанно: чем меньше храним
    # голос сотрудников, тем меньше правовой и репутационный риск.
    audio_retention_days: int = 7

    # extra="ignore": в .env остаются переменные от прошлых версий и от смежных
    # инструментов — падать из-за них на старте неправильно, это не ошибка конфига.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def yandex_enabled(self) -> bool:
        return bool(self.yandex_api_key and self.yandex_folder_id)

    @property
    def gigaam_language_set(self) -> frozenset[str]:
        return frozenset(x.strip() for x in self.gigaam_languages.split(",") if x.strip())

    @model_validator(mode="after")
    def _check_consistency(self) -> "Settings":
        """Поймать невозможные комбинации до того, как их поймает пилот."""
        if self.asr_provider == "gigaam" and not self.gigaam_url:
            raise ValueError(
                "ASR_PROVIDER=gigaam, но GIGAAM_URL пуст — некуда обращаться за распознаванием"
            )

        # Yandex нужен и для запасного распознавания, и для перевода, и для озвучки.
        needs_yandex = (
            self.asr_provider == "yandex" or self.asr_fallback_provider == "yandex"
        )
        if needs_yandex and not self.yandex_enabled and self.env == "prod":
            raise ValueError(
                "В проде нужен речевой стек Yandex: заполни YANDEX_API_KEY и YANDEX_FOLDER_ID"
            )

        if self.env == "prod":
            if len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY в проде должен быть не короче 32 символов")
            if self.debug:
                raise ValueError("DEBUG=true в проде запрещён — утечёт внутрянка в ответы")
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite в проде не используем — только PostgreSQL")

        return self


settings = Settings()  # type: ignore[call-arg]
