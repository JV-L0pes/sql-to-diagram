from enum import Enum


class InvalidDialectError(ValueError):
    def __init__(self, value: str):
        super().__init__(f"Unknown SQL dialect: {value!r}")


class SqlDialect(str, Enum):
    POSTGRES = "postgres"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MSSQL = "mssql"

    @classmethod
    def from_string(cls, value: str) -> "SqlDialect":
        normalized = value.strip().lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise InvalidDialectError(value)
