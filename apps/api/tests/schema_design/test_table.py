from src.schema_design.domain.table import Column, Table


def test_table_find_column_returns_matching_column():
    id_col = Column(name="id", type="INTEGER", nullable=False, primary_key=True)
    email_col = Column(name="email", type="VARCHAR(255)", nullable=False, primary_key=False)
    table = Table(name="users", columns=[id_col, email_col])

    assert table.find_column("email") is email_col


def test_table_find_column_returns_none_when_missing():
    table = Table(name="users", columns=[])

    assert table.find_column("missing") is None


def test_column_unique_defaults_to_false_and_table_starts_without_unique_constraints():
    table = Table(name="users", columns=[Column("id", "INTEGER", False, True)])

    assert table.columns[0].unique is False
    assert table.unique_constraints == []
