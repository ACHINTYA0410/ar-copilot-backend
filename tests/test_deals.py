import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_list_deals_empty(client):
    r = await client.get("/api/v1/deals")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data


async def test_create_and_get_deal(client):
    payload = {
        "customer_name": "Test School Pvt Ltd",
        "amount": 1500000.00,
        "submitted_by_name": "Test User",
        "submitted_by_zone": "Test Zone",
        "submitted_at": "2026-05-01T10:00:00Z",
        "products": ["Stitch LMS"],
    }
    create_r = await client.post("/api/v1/deals", json=payload)
    assert create_r.status_code == 201
    created = create_r.json()
    deal_id = created["id"]

    get_r = await client.get(f"/api/v1/deals/{deal_id}")
    assert get_r.status_code == 200
    assert get_r.json()["customer_name"] == "Test School Pvt Ltd"


async def test_get_deal_not_found(client):
    r = await client.get("/api/v1/deals/DL-XXXXX")
    assert r.status_code == 404


async def test_deal_stats(client):
    r = await client.get("/api/v1/deals/stats")
    assert r.status_code == 200
    data = r.json()
    assert "needs_review" in data
    assert "stuck" in data
    assert "auto_approved_today" in data


async def test_update_deal_status(client):
    payload = {
        "customer_name": "Status Test School",
        "amount": 500000.00,
        "submitted_by_name": "Tester",
        "submitted_by_zone": "North",
        "submitted_at": "2026-05-01T10:00:00Z",
    }
    create_r = await client.post("/api/v1/deals", json=payload)
    assert create_r.status_code == 201
    deal_id = create_r.json()["id"]

    patch_r = await client.patch(f"/api/v1/deals/{deal_id}", json={"status": "approved"})
    assert patch_r.status_code == 200
    assert patch_r.json()["status"] == "approved"
