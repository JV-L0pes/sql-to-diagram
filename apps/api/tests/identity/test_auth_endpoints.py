def test_register_then_login_then_access_protected_route(client):
    register = client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "correct horse battery staple"},
    )
    assert register.status_code == 201
    assert register.json()["email"] == "a@example.com"

    login = client.post(
        "/api/auth/login",
        json={"email": "a@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    tokens = login.json()
    assert "access_token" in tokens and "refresh_token" in tokens

    protected = client.get(
        "/api/projects", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert protected.status_code == 200
    assert protected.json() == []


def test_register_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "correct horse battery staple"}
    client.post("/api/auth/register", json=payload)

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "b@example.com", "password": "correct horse battery staple"},
    )

    response = client.post("/api/auth/login", json={"email": "b@example.com", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_accessing_a_protected_route_without_a_token_returns_401(client):
    response = client.get("/api/projects")

    assert response.status_code == 401


def test_refresh_then_logout_flow(client):
    client.post(
        "/api/auth/register",
        json={"email": "c@example.com", "password": "correct horse battery staple"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": "c@example.com", "password": "correct horse battery staple"},
    )
    refresh_token = login.json()["refresh_token"]

    refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    new_tokens = refreshed.json()

    # old refresh token is now revoked
    reused = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401

    logout = client.post("/api/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout.status_code == 204
