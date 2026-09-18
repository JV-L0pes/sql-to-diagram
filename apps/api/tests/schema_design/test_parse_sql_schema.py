from src.schema_design.application.parse_sql_schema import parse_sql_schema
from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.relationship import RelationshipSource, RelationshipType


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


def test_parse_sql_schema_produces_exact_relationship_set_across_all_relationship_kinds():
    """End-to-end pipeline test covering explicit table-level FK, inline REFERENCES FK,
    a many-to-many junction table, and a naming-convention-inferred relationship, all in
    one script. This is the test that should have caught the junction-table
    spurious-inference bug (Finding 1 of the final whole-branch review).
    """
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE categories (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id),
      category_id INTEGER
    );
    CREATE TABLE tags (id SERIAL PRIMARY KEY);
    CREATE TABLE post_tags (
      post_id INTEGER NOT NULL,
      tag_id INTEGER NOT NULL,
      PRIMARY KEY (post_id, tag_id),
      FOREIGN KEY (post_id) REFERENCES posts(id),
      FOREIGN KEY (tag_id) REFERENCES tags(id)
    );
    """

    result = parse_sql_schema(sql, SqlDialect.POSTGRES)

    actual = {
        (r.from_table, r.from_column, r.to_table, r.to_column, r.type, r.source)
        for r in result.relationships
    }
    expected = {
        (
            "posts",
            "user_id",
            "users",
            "id",
            RelationshipType.MANY_TO_ONE,
            RelationshipSource.EXPLICIT,
        ),
        (
            "posts",
            "category_id",
            "categories",
            "id",
            RelationshipType.MANY_TO_ONE,
            RelationshipSource.INFERRED,
        ),
        (
            "posts",
            "id",
            "tags",
            "id",
            RelationshipType.MANY_TO_MANY,
            RelationshipSource.EXPLICIT,
        ),
        (
            "tags",
            "id",
            "posts",
            "id",
            RelationshipType.MANY_TO_MANY,
            RelationshipSource.EXPLICIT,
        ),
    }

    assert actual == expected


def test_parse_sql_schema_handles_pg_dump_style_alter_table_foreign_keys():
    """pg_dump structures its output as CREATE TABLE statements for all tables,
    followed by separate ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY statements.
    """
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL);
    ALTER TABLE posts ADD CONSTRAINT fk_posts_user FOREIGN KEY (user_id) REFERENCES users(id);
    """

    result = parse_sql_schema(sql, SqlDialect.POSTGRES)

    explicit = [r for r in result.relationships if r.source == RelationshipSource.EXPLICIT]
    assert len(explicit) == 1
    assert explicit[0].from_table == "posts"
    assert explicit[0].from_column == "user_id"
    assert explicit[0].to_table == "users"
    assert explicit[0].to_column == "id"
