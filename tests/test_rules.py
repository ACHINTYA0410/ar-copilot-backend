import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_list_rules(client):
    r = await client.get("/api/v1/rules")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


async def test_get_rule(client):
    r = await client.get("/api/v1/rules/rule_check_signatures")
    assert r.status_code == 200
    assert r.json()["id"] == "rule_check_signatures"


async def test_get_rule_not_found(client):
    r = await client.get("/api/v1/rules/rule_does_not_exist")
    assert r.status_code == 404


async def test_list_checklists(client):
    r = await client.get("/api/v1/checklists")
    assert r.status_code == 200
    assert "items" in r.json()


async def test_audit_log(client):
    r = await client.get("/api/v1/audit-log")
    assert r.status_code == 200
    assert "items" in r.json()


async def test_audit_stats(client):
    r = await client.get("/api/v1/audit-log/stats")
    assert r.status_code == 200
    data = r.json()
    assert "compliance_score" in data
    assert "weekly_trend" in data
