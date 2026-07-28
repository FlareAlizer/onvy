from pydantic import BaseModel, Field


class ProductIn(BaseModel):
    """Данные для добавления позиции в базу знаний магазина."""

    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="", max_length=120)
    price: int = Field(default=0, ge=0)
    stock: int = Field(default=0, ge=0)
    location: str = Field(default="", max_length=120, description="Где лежит (стеллаж/зона)")
    description: str = Field(default="", description="Характеристики")
    aliases: str = Field(default="", description="Синонимы через запятую")


class ProductOut(BaseModel):
    """Позиция каталога в ответах API."""

    id: int
    name: str
    category: str
    price: int
    stock: int
    location: str
    description: str
    aliases: str

    model_config = {"from_attributes": True}


class ProductBulkIn(BaseModel):
    """Массовая загрузка каталога магазина."""

    items: list[ProductIn]
