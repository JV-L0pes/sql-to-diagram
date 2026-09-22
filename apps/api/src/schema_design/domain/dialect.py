from enum import StrEnum


class InvalidDialectError(ValueError):
    def __init__(self, value: str):
        super().__init__(f"Unknown SQL dialect: {value!r}")


class SqlDialect(StrEnum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MSSQL = "mssql"

    @classmethod
    def from_string(cls, value: str) -> "SqlDialect":
        normalized = value.strip().lower()
        alias = _ALIASES.get(normalized)
        if alias is not None:
            return alias
        raise InvalidDialectError(value)


_ALIASES = {
    "postgres": SqlDialect.POSTGRES,
    "postgresql": SqlDialect.POSTGRES,
    "pg": SqlDialect.POSTGRES,
    "mysql": SqlDialect.MYSQL,
    "mariadb": SqlDialect.MYSQL,
    "sqlite": SqlDialect.SQLITE,
    "sqlite3": SqlDialect.SQLITE,
    "mssql": SqlDialect.MSSQL,
    "sqlserver": SqlDialect.MSSQL,
    "sql_server": SqlDialect.MSSQL,
    "tsql": SqlDialect.MSSQL,
}
