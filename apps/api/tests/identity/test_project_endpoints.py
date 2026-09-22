def _register_and_login(client, email="proj@example.com"):
    password = "correct horse battery staple"
    client.post("/api/auth/register", json={"email": email, "password": password})
    login = client.post("/api/auth/login", json={"email": email, "password": password})
    return login.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_list_get_update_delete_project_flow(client):
    token = _register_and_login(client)
    headers = _auth_headers(token)

    create = client.post(
        "/api/projects",
        json={"name": "My Schema", "sql": "CREATE TABLE t(id INT);", "dialect": "postgres"},
        headers=headers,
    )
    assert create.status_code == 201
    project_id = create.json()["id"]

    listed = client.get("/api/projects", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(f"/api/projects/{project_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["sql"] == "CREATE TABLE t(id INT);"

    updated = client.put(
        f"/api/projects/{project_id}",
        json={"name": "Renamed", "sql": "CREATE TABLE u(id INT);", "dialect": "mysql"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    deleted = client.delete(f"/api/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204

    gone = client.get(f"/api/projects/{project_id}", headers=headers)
    assert gone.status_code == 404


def test_a_user_cannot_access_another_users_project(client):
    token_a = _register_and_login(client, email="owner@example.com")
    token_b = _register_and_login(client, email="intruder@example.com")

    create = client.post(
        "/api/projects",
        json={"name": "Private", "sql": "...", "dialect": "postgres"},
        headers=_auth_headers(token_a),
    )
    project_id = create.json()["id"]

    response = client.get(f"/api/projects/{project_id}", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_projects_endpoints_require_authentication(client):
    response = client.post("/api/projects", json={"name": "X", "sql": "...", "dialect": "postgres"})

    assert response.status_code == 401


def test_create_project_rejects_invalid_dialect(client):
    token = _register_and_login(client, email="invalid-dialect@example.com")

    response = client.post(
        "/api/projects",
        json={"name": "X", "sql": "...", "dialect": "not-a-real-dialect"},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


def test_list_projects_supports_limit_and_offset(client):
    token = _register_and_login(client, email="pagination@example.com")
    headers = _auth_headers(token)
    for index in range(3):
        client.post(
            "/api/projects",
            json={"name": f"P{index}", "sql": "...", "dialect": "postgres"},
            headers=headers,
        )

    first_page = client.get("/api/projects?limit=2", headers=headers)
    second_page = client.get("/api/projects?limit=2&offset=2", headers=headers)

    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 1


def test_list_projects_rejects_invalid_pagination(client):
    token = _register_and_login(client, email="bad-pagination@example.com")

    response = client.get("/api/projects?limit=0", headers=_auth_headers(token))

    assert response.status_code == 422
