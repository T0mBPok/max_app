import httpx

from src.main import app


def test_required_routes_are_documented():
    paths = app.openapi()["paths"]
    assert "/api/v1/rooms/{room_id}/join" in paths
    assert "/api/v1/admin/imports/{source_code}/run" in paths
    assert "/api/v1/admin/imports/sources" in paths
    assert "/api/v1/admin/imports/events/run" in paths
    assert "/api/v1/admin/imports/volunteering/run" in paths
    assert "/api/v1/dev/users" in paths
    assert "/docs" not in paths


async def test_health_and_uniform_errors():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/health")
        unauthorized = await client.get("/api/v1/rooms")
        invalid = await client.post("/api/v1/dev/users", json={})

    assert health.json() == {"status": "ok"}
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "FORBIDDEN"

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
