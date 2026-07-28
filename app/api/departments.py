"""Отделы: создание, ростер участников и QR-приглашение для онбординга жюри."""

import re
from urllib.parse import quote

import segno
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.deps import require_api_key
from app.models.department import Department
from app.models.employee import Employee
from app.schemas.department import DepartmentIn, DepartmentOut, Member
from app.services import departments as dept_service
from app.services.comms import manager

router = APIRouter(tags=["departments"], dependencies=[Depends(require_api_key)])


@router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(db: AsyncSession = Depends(get_session)) -> list[Department]:
    """Список отделов (и создание дефолтного, если ещё нет)."""
    await dept_service.get_or_create_default(db)
    await db.commit()  # зафиксировать дефолтный отдел, иначе он откатится
    return list((await db.execute(select(Department))).scalars().all())


@router.post("/departments", response_model=DepartmentOut, status_code=status.HTTP_201_CREATED)
async def create_department(
    payload: DepartmentIn, db: AsyncSession = Depends(get_session)
) -> Department:
    dept = Department(name=payload.name)
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    return dept


@router.get("/departments/{department_id}/members", response_model=list[Member])
async def members(department_id: int, db: AsyncSession = Depends(get_session)) -> list[Member]:
    """Ростер отдела с онлайн-статусом (для менеджера)."""
    rows = (
        (await db.execute(select(Employee).where(Employee.department_id == department_id)))
        .scalars()
        .all()
    )
    return [
        Member(
            id=e.id,
            name=e.name,
            role=e.role.value,
            language=e.language,
            online=manager.is_online(e.id),
        )
        for e in rows
    ]


@router.get("/departments/{department_id}/qr")
async def department_qr(
    department_id: int,
    base: str = Query(..., description="Origin клиента, напр. https://host:port"),
    db: AsyncSession = Depends(get_session),
) -> Response:
    """QR-код со ссылкой присоединения к отделу как сотрудник.

    Жюри сканирует → открывается страница входа с предзаполненным отделом и
    ключом доступа (на демо ключ общий). Возвращает SVG.
    """
    if await db.get(Department, department_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Отдел не найден")
    join_url = (
        f"{base.rstrip('/')}/?key={quote(settings.api_key)}&dept={department_id}&role=employee"
    )
    qr = segno.make(join_url, error="m")
    # svg_inline даёт <svg width=".." height=".."> БЕЗ viewBox: если клиент задаёт
    # размер через CSS, картинка обрезается. Заменяем фиксированные width/height на
    # viewBox + адаптивный размер (100%), чтобы QR масштабировался, а не кропался.
    width, height = qr.symbol_size(scale=1, border=4)
    body = qr.svg_inline(scale=1, border=4)
    body = re.sub(
        r'<svg width="\d+" height="\d+"',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" height="100%" preserveAspectRatio="xMidYMid meet"',
        body,
        count=1,
    )
    return Response(content=body, media_type="image/svg+xml")
