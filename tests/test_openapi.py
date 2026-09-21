from app.main import app


def test_required_routes_are_documented():
    paths = app.openapi()["paths"]
    assert "/api/v1/rooms/{room_id}/join" in paths
    assert "/api/v1/admin/imports/{source_code}/run" in paths
    assert "/api/v1/dev/users" in paths
    assert "/docs" not in paths
