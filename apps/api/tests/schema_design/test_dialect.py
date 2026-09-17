import pytest

from src.schema_design.domain.dialect import InvalidDialectError, SqlDialect


def test_from_string_accepts_known_dialects():
    assert SqlDialect.from_string("postgres") is SqlDialect.POSTGRES
    assert SqlDialect.from_string("MySQL") is SqlDialect.MYSQL
    assert SqlDialect.from_string("sqlite") is SqlDialect.SQLITE
    assert SqlDialect.from_string("mssql") is SqlDialect.MSSQL


def test_from_string_rejects_unknown_dialect():
    with pytest.raises(InvalidDialectError, match="oracle"):
        SqlDialect.from_string("oracle")
