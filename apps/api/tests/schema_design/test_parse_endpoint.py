import pytest


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


def test_parse_endpoint_returns_400_for_mismatched_composite_foreign_key(client):
    payload = {
        "sql": (
            "CREATE TABLE order_items ("
            "order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, "
            "FOREIGN KEY (order_id, product_id) REFERENCES orders(id));"
        ),
        "dialect": "postgres",
    }

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"


@pytest.mark.parametrize("sql", ["", "   \n  "])
def test_parse_endpoint_returns_400_for_empty_sql(client, sql):
    response = client.post("/api/schema/parse", json={"sql": sql, "dialect": "postgres"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"


def test_parse_endpoint_returns_400_for_tokenizer_error(client):
    payload = {"sql": "CREATE TABLE t (name TEXT 'unterminated", "dialect": "postgres"}

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"


def test_parse_endpoint_handles_bare_references_without_500(client):
    payload = {
        "sql": (
            "CREATE TABLE users (id SERIAL PRIMARY KEY);"
            "CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users);"
        ),
        "dialect": "postgres",
    }

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 200
    assert response.json()["relationships"][0]["to_column"] == "id"


def test_parse_endpoint_rejects_oversized_sql(client):
    payload = {"sql": "CREATE TABLE t (x INT);" + ("-- padding\n" * 50_000), "dialect": "postgres"}

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 422


def test_parse_endpoint_returns_400_for_deeply_nested_sql(client):
    payload = {"sql": f"SELECT {'(' * 100}1{')' * 100};", "dialect": "postgres"}

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"
