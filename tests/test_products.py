from httpx import AsyncClient


async def test_create_and_list_product(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/products",
        json={
            "name": "Наушники Sony WH-1000XM5",
            "category": "аудио",
            "price": 34990,
            "stock": 4,
            "aliases": "сони, наушники, беспроводные",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["price"] == 34990

    listed = await client.get("/api/products")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_bulk_upload(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/products/bulk",
        json={
            "items": [
                {"name": "Дрель Bosch", "price": 5990, "stock": 12, "location": "зона B2"},
                {"name": "Пылесос Dyson", "price": 54990, "stock": 2, "location": "зона D4"},
            ]
        },
    )
    assert resp.status_code == 201
    assert resp.json() == {"created": 2}
    assert len((await client.get("/api/products")).json()) == 2
