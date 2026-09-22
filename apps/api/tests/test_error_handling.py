import json
import logging

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.main import create_app
from src.shared_kernel.db import get_db
from src.shared_kernel.errors import error_body


def test_error_body_shape() -> None:
    assert error_body("internal_error", "boom") == {
        "error": {"code": "internal_error", "message": "boom"}
    }


def test_error_body_includes_details_when_given() -> None:
    body = error_body("internal_error", "boom", details={"field": "x"})
    assert body["error"]["details"] == {"field": "x"}


def test_unhandled_exception_returns_shared_error_body() -> None:
    """Proves the global exception handler registered in create_app() is wired up.

    A route is added that always raises, exercising the real handler
    (rather than unit-testing error_body() in isolation).
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSessionLocal = sessionmaker(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    @app.get("/api/_test/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/_test/boom")

    assert response.status_code == 500
    # The raw exception message must never leak to the client; only a
    # generic message is returned (the real error is logged server-side).
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal Server Error"}
    }


def test_http_exception_uses_the_shared_error_body(client):
    response = client.get("/api/projects")  # no bearer token -> HTTPBearer 401

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "http_401"
    assert "detail" not in body


def test_validation_error_uses_the_shared_error_body_without_echoing_input(client):
    response = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "short"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "not-an-email" not in json.dumps(body)
    assert "short" not in json.dumps(body)


def test_validation_error_log_never_contains_the_submitted_password(client, caplog):
    oversized_password = "SuperSecretPassword" * 10  # > 128 chars -> validation failure
    with caplog.at_level(logging.INFO, logger="src.main"):
        response = client.post(
            "/api/auth/register",
            json={"email": "ok@example.com", "password": oversized_password},
        )

    assert response.status_code == 422
    assert oversized_password not in caplog.text
