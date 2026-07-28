"""Обучение: генерация курса (мок LLM), прогресс, очки за прохождение."""

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import llm

_COURSE = {
    "title": "Работа с возражением «Дорого»",
    "description": "Учимся переводить цену в ценность.",
    "category": "Sales",
    "steps": [
        {"id": "s1", "type": "content", "title": "Урок", "content": "Сравнивайте с ценностью..."},
        {
            "id": "s2",
            "type": "quiz",
            "title": "Проверка",
            "question": {
                "text": "Клиент говорит «дорого». Что делать?",
                "options": ["Скидка сразу", "Выяснить, с чем сравнивает"],
                "correctOption": 1,
            },
        },
    ],
}


@pytest.fixture
def course_llm_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "yandex_api_key", "test", raising=False)
    monkeypatch.setattr(settings, "yandex_folder_id", "folder", raising=False)

    async def fake_complete_json(*args, **kwargs) -> dict:
        return _COURSE

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)


async def test_generate_and_list_course(client: AsyncClient, course_llm_stub: None) -> None:
    resp = await client.post(
        "/api/courses/generate", json={"topic": "Возражение дорого", "material": ""}
    )
    assert resp.status_code == 201
    course = resp.json()
    assert course["title"].startswith("Работа с возражением")
    assert len(course["steps"]) == 2

    listed = (await client.get("/api/courses")).json()
    assert len(listed) == 1


async def test_progress_awards_points_once(client: AsyncClient, course_llm_stub: None) -> None:
    emp = (await client.post("/api/employees", json={"name": "Иван"})).json()
    course = (await client.post("/api/courses/generate", json={"topic": "Тема"})).json()

    # Промежуточный прогресс — очков нет.
    await client.post(
        "/api/courses/progress",
        json={"employee_id": emp["id"], "course_id": course["id"], "progress": 50},
    )
    stats = (await client.get(f"/api/dashboard/employee/{emp['id']}")).json()
    assert stats["points"] == 0

    # Завершение — +25 очков, повторное завершение очков не добавляет.
    await client.post(
        "/api/courses/progress",
        json={"employee_id": emp["id"], "course_id": course["id"], "progress": 100},
    )
    await client.post(
        "/api/courses/progress",
        json={"employee_id": emp["id"], "course_id": course["id"], "progress": 100},
    )
    stats = (await client.get(f"/api/dashboard/employee/{emp['id']}")).json()
    assert stats["points"] == 25

    # Прогресс сотрудника виден в списке курсов.
    listed = (await client.get(f"/api/courses?employee_id={emp['id']}")).json()
    assert listed[0]["progress"] == 100


async def test_generate_requires_yandex(client: AsyncClient) -> None:
    resp = await client.post("/api/courses/generate", json={"topic": "Тема"})
    assert resp.status_code == 503
