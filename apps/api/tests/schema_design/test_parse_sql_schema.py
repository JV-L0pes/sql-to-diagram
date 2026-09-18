from src.schema_design.application.parse_sql_schema import parse_sql_schema
from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.relationship import RelationshipSource


def test_parse_sql_schema_returns_tables_relationships_and_warnings():
    sql = """
    CREATE TABLE users (
      id SERIAL PRIMARY KEY,
      email VARCHAR(255) NOT NULL
    );
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE logs (
      message TEXT
    );
    """

    result = parse_sql_schema(sql, SqlDialect.POSTGRES)

    assert {t.name for t in result.tables} == {"users", "posts", "logs"}
    assert len(result.relationships) == 1
    assert result.relationships[0].source == RelationshipSource.EXPLICIT
    assert any(w.table == "logs" for w in result.warnings)


def test_parse_sql_schema_combines_explicit_and_inferred_relationships():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE categories (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      category_id INTEGER,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    result = parse_sql_schema(sql, SqlDialect.POSTGRES)

    sources = {(r.from_column, r.source) for r in result.relationships}
    assert ("user_id", RelationshipSource.EXPLICIT) in sources
    assert ("category_id", RelationshipSource.INFERRED) in sources
