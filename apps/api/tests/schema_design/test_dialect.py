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


def test_from_string_accepts_common_aliases():
    assert SqlDialect.from_string("PostgreSQL") is SqlDialect.POSTGRES
    assert SqlDialect.from_string("postgres") is SqlDialect.POSTGRES
    assert SqlDialect.from_string("mariadb") is SqlDialect.MYSQL
    assert SqlDialect.from_string("SQLServer") is SqlDialect.MSSQL
    assert SqlDialect.from_string("sqlite3") is SqlDialect.SQLITE
