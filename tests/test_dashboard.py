from httpx import AsyncClient


async def _employee(client: AsyncClient, name: str, role: str = "employee") -> int:
    return (await client.post("/api/employees", json={"name": name, "role": role})).json()["id"]


async def test_goal_flow_awards_points(client: AsyncClient) -> None:
    emp = await _employee(client, "Иван")
    goal = (
        await client.post(
            "/api/goals",
            json={"employee_id": emp, "title": "5 подсказок", "target": 2, "reward_points": 50},
        )
    ).json()

    # Первый шаг — прогресс, но не выполнено.
    r1 = (await client.post(f"/api/goals/{goal['id']}/advance")).json()
    assert r1["progress"] == 1 and r1["done"] is False

    # Второй шаг — цель закрыта, награда начислена.
    r2 = (await client.post(f"/api/goals/{goal['id']}/advance")).json()
    assert r2["done"] is True

    stats = (await client.get(f"/api/dashboard/employee/{emp}")).json()
    assert stats["points"] == 50


async def test_goal_award_is_idempotent(client: AsyncClient) -> None:
    emp = await _employee(client, "Иван")
    goal = (
        await client.post(
            "/api/goals",
            json={"employee_id": emp, "title": "цель", "target": 1, "reward_points": 30},
        )
    ).json()
    await client.post(f"/api/goals/{goal['id']}/advance")
    await client.post(f"/api/goals/{goal['id']}/advance")  # повтор на выполненной

    stats = (await client.get(f"/api/dashboard/employee/{emp}")).json()
    assert stats["points"] == 30  # награда начислена ровно один раз


async def test_rop_dashboard_counts_messages(client: AsyncClient) -> None:
    ivan = await _employee(client, "Иван")
    await _employee(client, "Пётр")
    await client.post("/api/comms/messages", json={"sender_id": ivan, "text": "смена началась"})

    d = (await client.get("/api/dashboard/rop")).json()
    assert d["total_messages"] == 1
    assert len(d["team"]) == 2
    ivan_row = next(e for e in d["team"] if e["employee_id"] == ivan)
    assert ivan_row["messages_sent"] == 1
    assert ivan_row["points"] == 1  # POINTS_MESSAGE
