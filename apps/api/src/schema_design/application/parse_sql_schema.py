from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.parsed_schema import ParsedSchema
from src.schema_design.infrastructure.relationship_detector import (
    detect_explicit_relationships,
    detect_inferred_relationships,
)
from src.schema_design.infrastructure.sqlglot_parser import extract_foreign_keys, extract_tables
from src.schema_design.infrastructure.structural_validator import validate_structure


def parse_sql_schema(sql: str, dialect: SqlDialect) -> ParsedSchema:
    tables = extract_tables(sql, dialect)
    foreign_keys = extract_foreign_keys(sql, dialect)

    explicit_relationships = detect_explicit_relationships(tables, foreign_keys)
    inferred_relationships = detect_inferred_relationships(tables, explicit_relationships)
    relationships = explicit_relationships + inferred_relationships

    warnings = validate_structure(tables, relationships)

    return ParsedSchema(tables=tables, relationships=relationships, warnings=warnings)
