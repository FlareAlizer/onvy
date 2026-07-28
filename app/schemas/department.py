from pydantic import BaseModel, Field


class DepartmentIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class DepartmentOut(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class Member(BaseModel):
    """Участник отдела в ростере (для менеджера)."""

    id: int
    name: str
    role: str
    language: str
    online: bool
