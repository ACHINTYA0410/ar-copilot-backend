import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def test_deal_id(client):
    r = await client.post(
        "/api/v1/deals",
        json={
            "customer_name": "Validation Test Co",
            "amount": 1000000.0,
            "submitted_by_name": "Tester",
            "submitted_by_zone": "West",
            "submitted_at": "2026-05-01T10:00:00Z",
        },
    )
    return r.json()["id"]


async def test_trigger_validation(client, test_deal_id):
    r = await client.post(f"/api/v1/deals/{test_deal_id}/validate")
    assert r.status_code == 202
    data = r.json()
    assert "validation_run_id" in data
    assert data["deal_id"] == test_deal_id


async def test_get_validation_run(client, test_deal_id):
    trigger_r = await client.post(f"/api/v1/deals/{test_deal_id}/validate")
    run_id = trigger_r.json()["validation_run_id"]

    get_r = await client.get(f"/api/v1/validation-runs/{run_id}")
    assert get_r.status_code == 200
    data = get_r.json()
    assert data["deal_id"] == test_deal_id
    assert "status" in data


async def test_validation_run_not_found(client):
    r = await client.get("/api/v1/validation-runs/nonexistent-id")
    assert r.status_code == 404
