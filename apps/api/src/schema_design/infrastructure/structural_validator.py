import re

from src.schema_design.domain.relationship import Relationship, RelationshipSource
from src.schema_design.domain.table import Table
from src.schema_design.domain.warning import SchemaWarning, WarningCode

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_NON_ATOMIC_TYPE_MARKERS = ("[]", "ARRAY", "JSON", "JSONB")


def validate_structure(
    tables: list[Table], relationships: list[Relationship]
) -> list[SchemaWarning]:
    warnings: list[SchemaWarning] = []

    for table in tables:
        warnings.extend(_check_missing_primary_key(table))
        warnings.extend(_check_non_atomic_columns(table))
        warnings.extend(_check_naming_convention(table))

    warnings.extend(_check_nullable_foreign_keys(tables, relationships))

    return warnings


def _check_missing_primary_key(table: Table) -> list[SchemaWarning]:
    if any(column.primary_key for column in table.columns):
        return []
    return [
        SchemaWarning(
            code=WarningCode.MISSING_PRIMARY_KEY,
            table=table.name,
            message=f"Table '{table.name}' has no primary key.",
        )
    ]


def _check_non_atomic_columns(table: Table) -> list[SchemaWarning]:
    warnings = []
    for column in table.columns:
        upper_type = column.type.upper()
        if any(marker in upper_type for marker in _NON_ATOMIC_TYPE_MARKERS):
            warnings.append(
                SchemaWarning(
                    code=WarningCode.NON_ATOMIC_COLUMN_TYPE,
                    table=table.name,
                    message=(
                        f"Column '{table.name}.{column.name}' has a non-atomic type "
                        f"({column.type})."
                    ),
                )
            )
    return warnings


def _check_naming_convention(table: Table) -> list[SchemaWarning]:
    warnings = []
    if not _SNAKE_CASE_RE.match(table.name):
        warnings.append(
            SchemaWarning(
                code=WarningCode.NON_SNAKE_CASE_IDENTIFIER,
                table=table.name,
                message=f"Table name '{table.name}' is not snake_case.",
            )
        )
    for column in table.columns:
        if not _SNAKE_CASE_RE.match(column.name):
            warnings.append(
                SchemaWarning(
                    code=WarningCode.NON_SNAKE_CASE_IDENTIFIER,
                    table=table.name,
                    message=f"Column '{table.name}.{column.name}' is not snake_case.",
                )
            )
    return warnings


def _check_nullable_foreign_keys(
    tables: list[Table], relationships: list[Relationship]
) -> list[SchemaWarning]:
    warnings = []
    tables_by_name = {t.name: t for t in tables}

    for rel in relationships:
        if rel.source != RelationshipSource.EXPLICIT:
            continue
        source_table = tables_by_name.get(rel.from_table)
        if source_table is None:
            continue
        column = source_table.find_column(rel.from_column)
        if column is not None and column.nullable:
            warnings.append(
                SchemaWarning(
                    code=WarningCode.NULLABLE_FOREIGN_KEY,
                    table=rel.from_table,
                    message=(
                        f"Foreign key '{rel.from_table}.{rel.from_column}' is nullable, "
                        f"making the relationship to '{rel.to_table}' optional."
                    ),
                )
            )
    return warnings
