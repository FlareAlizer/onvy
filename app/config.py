from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из .env.

    Все секреты (SECRET_KEY, API_KEY) читаются только отсюда — не хардкодим.
    """

    # Инфраструктура
    database_url: str = "sqlite+aiosqlite:///./app.db"
    secret_key: str
    debug: bool = False

    # Простая аутентификация MVP: клиент шлёт этот ключ в заголовке X-API-Key.
    api_key: str

    # Язык по умолчанию для сотрудников/подсказок ассистента.
    default_language: str = "ru"

    # --- Yandex Cloud: ASR (SpeechKit STT), TTS, Translate ---
    # Если ключа нет — перевод падает на заглушку, а голосовые роуты вернут 503.
    yandex_api_key: str = ""
    yandex_folder_id: str = ""
    # Модель YandexGPT: "yandexgpt-lite" (быстро/дёшево) или "yandexgpt" (умнее,
    # лучше для глубокого разбора диалогов).
    yandex_gpt_model: str = "yandexgpt-lite"

    @property
    def yandex_enabled(self) -> bool:
        """Настроен ли реальный речевой стек Yandex."""
        return bool(self.yandex_api_key and self.yandex_folder_id)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()  # type: ignore[call-arg]
