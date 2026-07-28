from httpx import AsyncClient


async def test_employee_joins_default_department(client: AsyncClient) -> None:
    """Без department_id сотрудник попадает в дефолтный демо-отдел."""
    emp = (await client.post("/api/employees", json={"name": "Иван"})).json()
    assert emp["department_id"] is not None

    depts = (await client.get("/api/departments")).json()
    assert len(depts) == 1
    assert emp["department_id"] == depts[0]["id"]


async def test_roster_lists_members(client: AsyncClient) -> None:
    e1 = (await client.post("/api/employees", json={"name": "Иван"})).json()
    await client.post("/api/employees", json={"name": "Пётр", "department_id": e1["department_id"]})

    members = (await client.get(f"/api/departments/{e1['department_id']}/members")).json()
    assert len(members) == 2
    assert {m["online"] for m in members} == {False}  # никто не подключён по WS


async def test_qr_returns_svg(client: AsyncClient) -> None:
    emp = (await client.post("/api/employees", json={"name": "Иван"})).json()
    resp = await client.get(
        f"/api/departments/{emp['department_id']}/qr",
        params={"base": "http://localhost:8000"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in resp.text
    # viewBox обязателен — без него SVG обрезается при CSS-масштабировании.
    assert "viewBox=" in resp.text
    assert 'width="100%"' in resp.text


async def test_rejoin_reuses_account(client: AsyncClient) -> None:
    """Повторный вход с тем же именем не создаёт дубля — иначе рация уходит двойнику."""
    first = (await client.post("/api/employees", json={"name": "Иван", "language": "ru"})).json()
    second = (await client.post("/api/employees", json={"name": "иван", "language": "en"})).json()

    assert second["id"] == first["id"]  # тот же аккаунт (регистр не важен)
    assert second["language"] == "en"  # профиль обновился

    members = (await client.get(f"/api/departments/{first['department_id']}/members")).json()
    assert len(members) == 1  # дублей в списке нет


async def test_employee_changes_language(client: AsyncClient) -> None:
    emp = (await client.post("/api/employees", json={"name": "John", "language": "ru"})).json()
    updated = (await client.patch(f"/api/employees/{emp['id']}", json={"language": "en"})).json()
    assert updated["language"] == "en"
