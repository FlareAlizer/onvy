from fastapi import Header, HTTPException, status

from app.config import settings


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """Простая аутентификация MVP по ключу из заголовка X-API-Key.

    Ключ хранится только в .env (settings.api_key). На рост — заменить на
    OAuth2 + JWT по сотруднику.
    """
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный API-ключ",
        )
