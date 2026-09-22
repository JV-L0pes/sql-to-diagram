from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.parsed_schema import ParsedSchema
from src.schema_design.infrastructure.relationship_detector import (
    detect_explicit_relationships,
    detect_inferred_relationships,
)
from src.schema_design.infrastructure.sqlglot_parser import parse_sql
from src.schema_design.infrastructure.structural_validator import validate_structure


def parse_sql_schema(sql: str, dialect: SqlDialect) -> ParsedSchema:
    parsed = parse_sql(sql, dialect)

    explicit_relationships = detect_explicit_relationships(parsed.tables, parsed.foreign_keys)
    inferred_relationships = detect_inferred_relationships(
        parsed.tables, explicit_relationships, parsed.foreign_keys
    )
    relationships = explicit_relationships + inferred_relationships

    warnings = validate_structure(parsed.tables, relationships)

    return ParsedSchema(tables=parsed.tables, relationships=relationships, warnings=warnings)
