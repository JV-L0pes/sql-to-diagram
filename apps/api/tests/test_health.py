def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_returns_503_when_database_is_unavailable(client):
    from sqlalchemy.exc import OperationalError

    from src.shared_kernel.db import get_db

    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("down"))

    client.app.dependency_overrides[get_db] = lambda: _BrokenSession()

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


def test_health_503_error_body_is_documented_in_openapi(client):
    schema = client.app.openapi()
    response = schema["paths"]["/api/health"]["get"]["responses"]["503"]
    ref = response["content"]["application/json"]["schema"]["$ref"]

    assert ref.endswith("/ErrorResponse")
