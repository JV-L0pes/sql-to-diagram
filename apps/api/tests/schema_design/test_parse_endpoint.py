def test_parse_endpoint_returns_tables_relationships_warnings(client):
    payload = {
        "sql": (
            "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL);"
            "CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, "
            "FOREIGN KEY (user_id) REFERENCES users(id));"
        ),
        "dialect": "postgres",
    }

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 200
    body = response.json()
    table_names = {t["name"] for t in body["tables"]}
    assert table_names == {"users", "posts"}
    assert len(body["relationships"]) == 1
    assert body["relationships"][0]["source"] == "explicit"
    assert "warnings" in body


def test_parse_endpoint_returns_400_for_invalid_sql(client):
    payload = {"sql": "THIS IS NOT VALID SQL AT ALL (((", "dialect": "postgres"}

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"


def test_parse_endpoint_returns_400_for_invalid_dialect(client):
    payload = {"sql": "CREATE TABLE users (id INTEGER);", "dialect": "oracle"}

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 400
