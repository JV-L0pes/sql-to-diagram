import pytest

from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.infrastructure.sqlglot_parser import extract_foreign_keys, extract_tables


def test_extract_tables_reads_columns_and_column_level_primary_key():
    sql = """
    CREATE TABLE users (
      id SERIAL PRIMARY KEY,
      email VARCHAR(255) NOT NULL,
      bio TEXT
    );
    """

    tables = extract_tables(sql, SqlDialect.POSTGRES)

    assert len(tables) == 1
    users = tables[0]
    assert users.name == "users"
    assert len(users.columns) == 3

    id_col = users.find_column("id")
    assert id_col.primary_key is True
    assert id_col.nullable is False

    email_col = users.find_column("email")
    assert email_col.primary_key is False
    assert email_col.nullable is False

    bio_col = users.find_column("bio")
    assert bio_col.nullable is True
    assert bio_col.primary_key is False


def test_extract_tables_reads_table_level_composite_primary_key():
    sql = """
    CREATE TABLE order_items (
      order_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      quantity INTEGER NOT NULL,
      PRIMARY KEY (order_id, product_id)
    );
    """

    tables = extract_tables(sql, SqlDialect.POSTGRES)

    order_items = tables[0]
    assert order_items.find_column("order_id").primary_key is True
    assert order_items.find_column("product_id").primary_key is True
    assert order_items.find_column("quantity").primary_key is False


def test_extract_tables_handles_multiple_statements():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL);
    """

    tables = extract_tables(sql, SqlDialect.POSTGRES)

    assert [t.name for t in tables] == ["users", "posts"]


def test_extract_foreign_keys_from_table_level_constraint():
    sql = """
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    foreign_keys = extract_foreign_keys(sql, SqlDialect.POSTGRES)

    assert foreign_keys == [("posts", "user_id", "users", "id")]


def test_extract_foreign_keys_from_inline_column_reference():
    sql = """
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id)
    );
    """

    foreign_keys = extract_foreign_keys(sql, SqlDialect.POSTGRES)

    assert foreign_keys == [("posts", "user_id", "users", "id")]


def test_extract_foreign_keys_returns_empty_list_when_none_declared():
    sql = "CREATE TABLE users (id SERIAL PRIMARY KEY);"

    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == []


def test_extract_foreign_keys_raises_value_error_for_mismatched_composite_fk():
    sql = """
    CREATE TABLE order_items (
      order_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      FOREIGN KEY (order_id, product_id) REFERENCES orders(id)
    );
    """

    with pytest.raises(ValueError):
        extract_foreign_keys(sql, SqlDialect.POSTGRES)


def test_extract_foreign_keys_deduplicates_redundant_inline_and_table_level_fk():
    sql = """
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER REFERENCES users(id),
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    foreign_keys = extract_foreign_keys(sql, SqlDialect.POSTGRES)

    assert foreign_keys == [("posts", "user_id", "users", "id")]


def test_extract_foreign_keys_from_alter_table_add_constraint():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL);
    ALTER TABLE posts ADD CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id);
    """

    foreign_keys = extract_foreign_keys(sql, SqlDialect.POSTGRES)

    assert foreign_keys == [("posts", "user_id", "users", "id")]


DIALECT_CREATE_TABLE = {
    SqlDialect.POSTGRES: "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL);",
    SqlDialect.MYSQL: (
        "CREATE TABLE users (id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(255) NOT NULL);"
    ),
    SqlDialect.SQLITE: "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);",
    SqlDialect.MSSQL: (
        "CREATE TABLE users (id INT IDENTITY(1,1) PRIMARY KEY, email VARCHAR(255) NOT NULL);"
    ),
}


@pytest.mark.parametrize("dialect", list(SqlDialect))
def test_extract_tables_works_across_all_dialects(dialect):
    sql = DIALECT_CREATE_TABLE[dialect]

    tables = extract_tables(sql, dialect)

    assert len(tables) == 1
    users = tables[0]
    assert users.name == "users"
    id_col = users.find_column("id")
    assert id_col.primary_key is True
    email_col = users.find_column("email")
    assert email_col.nullable is False
