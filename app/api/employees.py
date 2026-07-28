from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import require_api_key
from app.models.employee import Employee
from app.schemas.employee import EmployeeIn, EmployeeOut, EmployeeUpdate
from app.services import departments as dept_service

router = APIRouter(tags=["employees"], dependencies=[Depends(require_api_key)])


@router.post("/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeIn, db: AsyncSession = Depends(get_session)) -> Employee:
    """Завести сотрудника. Без department_id — попадает в дефолтный демо-отдел.

    Повторный вход с тем же именем в том же отделе НЕ создаёт дубля — возвращаем
    существующий аккаунт, обновив роль/язык (иначе в списках появляются двойники,
    а рация уходит офлайн-дублю).
    """
    department_id = payload.department_id
    if department_id is None:
        department_id = (await dept_service.get_or_create_default(db)).id

    name = payload.name.strip()
    # Сравнение имён — в Python: lower() в SQLite не работает с кириллицей.
    dept_employees = (
        (await db.execute(select(Employee).where(Employee.department_id == department_id)))
        .scalars()
        .all()
    )
    existing = next((e for e in dept_employees if e.name.lower() == name.lower()), None)
    if existing is not None:
        existing.role = payload.role
        existing.language = payload.language
        await db.commit()
        await db.refresh(existing)
        return existing

    employee = Employee(
        name=name,
        role=payload.role,
        language=payload.language,
        department_id=department_id,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)
    return employee


@router.patch("/employees/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int, payload: EmployeeUpdate, db: AsyncSession = Depends(get_session)
) -> Employee:
    """Обновить профиль (язык/имя) — сотрудник меняет язык в личном кабинете."""
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    if payload.language is not None:
        employee.language = payload.language
    if payload.name is not None:
        employee.name = payload.name
    await db.commit()
    await db.refresh(employee)
    return employee


@router.get("/employees", response_model=list[EmployeeOut])
async def list_employees(db: AsyncSession = Depends(get_session)) -> list[Employee]:
    """Список сотрудников."""
    return list((await db.execute(select(Employee))).scalars().all())


@router.get("/employees/{employee_id}", response_model=EmployeeOut)
async def get_employee(employee_id: int, db: AsyncSession = Depends(get_session)) -> Employee:
    """Карточка сотрудника."""
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сотрудник не найден")
    return employee
