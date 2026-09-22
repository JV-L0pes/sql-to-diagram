from datetime import UTC, datetime

import pytest

from src.shared_kernel import rate_limit as rate_limit_module


@pytest.fixture()
def frozen_now(monkeypatch):
    moment = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(rate_limit_module, "utc_now", lambda: moment)
    return moment


def _login(client, ip="203.0.113.10"):
    return client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "wrong password"},
        headers={"x-forwarded-for": ip},
    )


def test_login_is_rate_limited_per_ip(client, frozen_now):
    for _ in range(10):
        assert _login(client).status_code == 401

    response = _login(client)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "http_429"
    assert response.headers["retry-after"] == "60"


def test_rate_limit_is_scoped_to_the_client_ip(client, frozen_now):
    for _ in range(11):
        _login(client, ip="198.51.100.7")

    other = _login(client, ip="198.51.100.8")

    assert other.status_code == 401  # different bucket


def test_register_is_rate_limited(client, frozen_now):
    for _ in range(5):
        client.post(
            "/api/auth/register",
            json={"email": "rl@example.com", "password": "correct horse battery staple"},
            headers={"x-forwarded-for": "203.0.113.99"},
        )

    response = client.post(
        "/api/auth/register",
        json={"email": "rl2@example.com", "password": "correct horse battery staple"},
        headers={"x-forwarded-for": "203.0.113.99"},
    )

    assert response.status_code == 429


def test_schema_parse_is_rate_limited(client, frozen_now):
    payload = {"sql": "CREATE TABLE t (id INTEGER PRIMARY KEY);", "dialect": "postgres"}

    for _ in range(30):
        assert client.post("/api/schema/parse", json=payload).status_code == 200

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 429
