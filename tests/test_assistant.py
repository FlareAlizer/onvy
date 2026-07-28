from httpx import AsyncClient


async def _seed_product(client: AsyncClient) -> None:
    await client.post(
        "/api/products",
        json={
            "name": "Наушники Sony WH-1000XM5",
            "category": "аудио",
            "price": 34990,
            "stock": 4,
            "description": "Беспроводные, шумоподавление.",
            "aliases": "сони, наушники, xm5",
        },
    )


async def test_assistant_finds_product(client: AsyncClient) -> None:
    await _seed_product(client)
    resp = await client.post(
        "/api/assistant/ask",
        json={"text": "Сколько стоят наушники Sony?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["matched"][0]["name"].startswith("Наушники Sony")
    assert "34990₽" in data["answer"]


async def test_assistant_no_match(client: AsyncClient) -> None:
    await _seed_product(client)
    resp = await client.post("/api/assistant/ask", json={"text": "холодильник"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
    assert data["matched"] == []
