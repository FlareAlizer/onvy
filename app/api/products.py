from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_api_key
from app.models.product import Product
from app.schemas.product import ProductBulkIn, ProductIn, ProductOut

router = APIRouter(tags=["products"], dependencies=[Depends(require_api_key)])


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductIn, db: AsyncSession = Depends(get_session)) -> Product:
    """Добавить позицию в базу знаний магазина."""
    product = Product(**payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.post("/products/bulk", status_code=status.HTTP_201_CREATED)
async def create_products_bulk(
    payload: ProductBulkIn, db: AsyncSession = Depends(get_session)
) -> dict[str, int]:
    """Массовая загрузка каталога: список товаров за один запрос."""
    for item in payload.items:
        db.add(Product(**item.model_dump()))
    await db.commit()
    return {"created": len(payload.items)}


@router.get("/products", response_model=list[ProductOut])
async def list_products(db: AsyncSession = Depends(get_session)) -> list[Product]:
    """Каталог магазина."""
    return list((await db.execute(select(Product))).scalars().all())
