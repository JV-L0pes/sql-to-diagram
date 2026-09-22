import re

from src.schema_design.domain.relationship import Relationship, RelationshipSource, RelationshipType
from src.schema_design.domain.table import Table


def detect_explicit_relationships(
    tables: list[Table],
    foreign_keys: list[tuple[str, str, str, str]],
) -> list[Relationship]:
    tables_by_name = {t.name: t for t in tables}
    junction_tables = _identify_junction_tables(tables, foreign_keys)

    relationships: list[Relationship] = []

    for from_table, from_column, to_table, to_column in foreign_keys:
        if from_table in junction_tables:
            continue
        rel_type = _determine_cardinality(
            tables_by_name, from_table, from_column, to_table, to_column
        )
        relationships.append(
            Relationship(
                from_table=from_table,
                from_column=from_column,
                to_table=to_table,
                to_column=to_column,
                type=rel_type,
                source=RelationshipSource.EXPLICIT,
            )
        )

    for junction_name in junction_tables:
        junction_fks = [fk for fk in foreign_keys if fk[0] == junction_name]
        if len(junction_fks) != 2:
            continue
        (_, _, table_a, col_a), (_, _, table_b, col_b) = junction_fks
        relationships.append(
            Relationship(
                table_a,
                col_a,
                table_b,
                col_b,
                RelationshipType.MANY_TO_MANY,
                RelationshipSource.EXPLICIT,
                via_table=junction_name,
            )
        )
        relationships.append(
            Relationship(
                table_b,
                col_b,
                table_a,
                col_a,
                RelationshipType.MANY_TO_MANY,
                RelationshipSource.EXPLICIT,
                via_table=junction_name,
            )
        )

    return relationships


def _identify_junction_tables(
    tables: list[Table], foreign_keys: list[tuple[str, str, str, str]]
) -> set[str]:
    junction_tables: set[str] = set()

    for table in tables:
        fks_from_this_table = [fk for fk in foreign_keys if fk[0] == table.name]
        if len(fks_from_this_table) != 2:
            continue
        # Two FKs pointing at the same table is a self-referencing table, not a junction.
        if len({fk[2] for fk in fks_from_this_table}) != 2:
            continue

        fk_columns = {fk[1] for fk in fks_from_this_table}
        pk_columns = {c.name for c in table.columns if c.primary_key}
        unique_sets = {frozenset(cols) for cols in table.unique_constraints}

        if pk_columns == fk_columns or frozenset(fk_columns) in unique_sets:
            junction_tables.add(table.name)

    return junction_tables


def _is_column_unique(table: Table, column_name: str) -> bool:
    column = table.find_column(column_name)
    if column is None:
        return False
    if column.unique:
        return True
    if not column.primary_key:
        return False
    # A composite PK column is not individually unique.
    return sum(1 for c in table.columns if c.primary_key) == 1


def _determine_cardinality(
    tables_by_name: dict[str, Table],
    from_table: str,
    from_column: str,
    to_table: str,
    to_column: str,
) -> RelationshipType:
    from_tbl = tables_by_name.get(from_table)
    to_tbl = tables_by_name.get(to_table)
    if from_tbl is None or to_tbl is None:
        return RelationshipType.MANY_TO_ONE

    from_is_unique = _is_column_unique(from_tbl, from_column)
    to_is_unique = _is_column_unique(to_tbl, to_column)

    if from_is_unique and to_is_unique:
        return RelationshipType.ONE_TO_ONE
    return RelationshipType.MANY_TO_ONE


def detect_inferred_relationships(
    tables: list[Table],
    explicit_relationships: list[Relationship],
    foreign_keys: list[tuple[str, str, str, str]],
) -> list[Relationship]:
    explicit_columns = {(fk[0], fk[1]) for fk in foreign_keys}
    explicit_columns.update((r.from_table, r.from_column) for r in explicit_relationships)
    tables_by_name = {t.name: t for t in tables}
    table_names = list(tables_by_name.keys())

    inferred: list[Relationship] = []

    for table in tables:
        for column in table.columns:
            if (table.name, column.name) in explicit_columns:
                continue
            if not column.name.endswith("_id"):
                continue

            target_table_name = _find_matching_table(column.name, table_names, exclude=table.name)
            if target_table_name is None:
                continue

            target_table = tables_by_name[target_table_name]
            primary_key_columns = [c for c in target_table.columns if c.primary_key]
            if len(primary_key_columns) != 1:
                continue
            target_column = primary_key_columns[0]

            if not _are_types_compatible(column.type, target_column.type):
                continue

            inferred.append(
                Relationship(
                    from_table=table.name,
                    from_column=column.name,
                    to_table=target_table_name,
                    to_column=target_column.name,
                    type=RelationshipType.MANY_TO_ONE,
                    source=RelationshipSource.INFERRED,
                )
            )

    return inferred


_INTEGER_TYPE_NAMES = {
    "int",
    "integer",
    "bigint",
    "smallint",
    "serial",
    "bigserial",
    "tinyint",
    "mediumint",
}
_STRING_TYPE_NAMES = {
    "varchar",
    "char",
    "character",
    "text",
    "string",
    "nvarchar",
    "nchar",
    "clob",
}
_DECIMAL_TYPE_NAMES = {"decimal", "numeric", "float", "double", "real", "money"}
_DATE_TYPE_NAMES = {"date", "datetime", "timestamp", "time"}


def _normalize_type(type_name: str) -> str:
    normalized = re.sub(r"\([^)]*\)", "", type_name).strip().lower()
    for suffix in (" unsigned", " zerofill"):
        normalized = normalized.replace(suffix, "")
    return normalized


def _type_category(type_name: str) -> str:
    normalized = _normalize_type(type_name)
    first_token = normalized.split()[0] if normalized.split() else ""
    for names, category in (
        (_INTEGER_TYPE_NAMES, "integer"),
        (_STRING_TYPE_NAMES, "string"),
        (_DECIMAL_TYPE_NAMES, "decimal"),
        (_DATE_TYPE_NAMES, "date"),
    ):
        if first_token in names:
            return category
    return normalized


def _are_types_compatible(type_a: str, type_b: str) -> bool:
    return _type_category(type_a) == _type_category(type_b)


def _find_matching_table(column_name: str, table_names: list[str], exclude: str) -> str | None:
    prefix = column_name[: -len("_id")].lower()
    candidates = {prefix, f"{prefix}s", f"{prefix}es", f"{prefix}a", f"{prefix}as"}
    if prefix.endswith("y"):
        candidates.add(f"{prefix[:-1]}ies")

    matches = [
        name
        for name in table_names
        if name != exclude and name.rsplit(".", 1)[-1].lower() in candidates
    ]
    # Ambiguous matches (>1) are skipped rather than guessed.
    if len(matches) != 1:
        return None
    return matches[0]
