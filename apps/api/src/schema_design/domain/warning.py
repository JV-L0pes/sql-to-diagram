from dataclasses import dataclass
from enum import Enum


class WarningCode(str, Enum):
    MISSING_PRIMARY_KEY = "missing_primary_key"
    NON_ATOMIC_COLUMN_TYPE = "non_atomic_column_type"
    NULLABLE_FOREIGN_KEY = "nullable_foreign_key"
    NON_SNAKE_CASE_IDENTIFIER = "non_snake_case_identifier"


@dataclass(frozen=True)
class SchemaWarning:
    code: WarningCode
    table: str
    message: str
