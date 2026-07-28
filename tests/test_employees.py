from httpx import AsyncClient


async def test_create_and_get_employee(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/employees",
        json={"name": "Иван", "role": "rop", "language": "ru"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Иван"
    assert data["role"] == "rop"

    got = await client.get(f"/api/employees/{data['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == data["id"]


async def test_list_employees(client: AsyncClient) -> None:
    await client.post("/api/employees", json={"name": "Петр"})
    resp = await client.get("/api/employees")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_requires_api_key(client: AsyncClient) -> None:
    resp = await client.get("/api/employees", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401
