from dataclasses import dataclass, replace

import sqlglot
from sqlglot import exp

from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.table import Column, Table

# sqlglot names its T-SQL dialect "tsql", not "mssql" — translate our domain
# dialect names to sqlglot's own before handing them to sqlglot's parser.
_SQLGLOT_DIALECT_NAMES = {SqlDialect.MSSQL: "tsql"}

# sqlglot renamed AlterTable -> Alter in v26; accept both so the parser keeps
# working if the dependency floor is ever relaxed.
_ALTER_NODE_TYPES = tuple(
    node_type
    for node_type in (getattr(exp, "AlterTable", None), getattr(exp, "Alter", None))
    if node_type is not None
)

ForeignKeyTuple = tuple[str, str, str, str]


@dataclass(frozen=True)
class ParsedSql:
    tables: list[Table]
    foreign_keys: list[ForeignKeyTuple]


def _sqlglot_dialect(dialect: SqlDialect) -> str:
    return _SQLGLOT_DIALECT_NAMES.get(dialect, dialect.value)


def _qualified_name(table_expr: exp.Table) -> str:
    """Keep the schema qualifier so same-named tables in different schemas stay distinct."""
    return f"{table_expr.db}.{table_expr.name}" if table_expr.db else table_expr.name


def parse_sql(sql: str, dialect: SqlDialect) -> ParsedSql:
    """Parse SQL text once and extract tables plus deduplicated foreign keys."""
    statements = sqlglot.parse(sql, read=_sqlglot_dialect(dialect))
    tables = _extract_tables(statements, dialect)
    _apply_alter_statements(statements, tables, dialect)
    foreign_keys = _extract_foreign_keys(statements, tables)
    return ParsedSql(tables=tables, foreign_keys=foreign_keys)


def extract_tables(sql: str, dialect: SqlDialect) -> list[Table]:
    """Parse SQL text and extract Table/Column domain objects for each CREATE TABLE statement."""
    return parse_sql(sql, dialect).tables


def extract_foreign_keys(sql: str, dialect: SqlDialect) -> list[ForeignKeyTuple]:
    """Parse SQL text and extract explicit FOREIGN KEY constraints in source order.

    Returns one (from_table, from_column, to_table, to_column) tuple per FK
    column pair. REFERENCES without a column list resolve to the target table's
    single-column primary key.
    """
    return parse_sql(sql, dialect).foreign_keys


def _extract_tables(statements: list[exp.Expression | None], dialect: SqlDialect) -> list[Table]:
    tables: list[Table] = []
    for statement in statements:
        if isinstance(statement, exp.Create) and statement.args.get("kind") == "TABLE":
            tables.append(_extract_table(statement, dialect))
    return tables


def _extract_table(create_stmt: exp.Create, dialect: SqlDialect) -> Table:
    schema_expr = create_stmt.this
    table_name = _qualified_name(schema_expr.this)

    column_defs = [item for item in schema_expr.expressions if isinstance(item, exp.ColumnDef)]
    primary_key_columns = _collect_primary_key_columns(schema_expr)
    single_unique, composite_unique = _collect_unique_constraints(schema_expr)

    columns = [
        _extract_column(column_def, dialect, primary_key_columns, single_unique)
        for column_def in column_defs
    ]
    return Table(name=table_name, columns=columns, unique_constraints=composite_unique)


def _collect_primary_key_columns(schema_expr: exp.Schema) -> set[str]:
    names: set[str] = set()
    for primary_key in schema_expr.find_all(exp.PrimaryKey):
        names.update(column.name for column in primary_key.expressions)
    for constraint in schema_expr.find_all(exp.Constraint):
        # MSSQL "CONSTRAINT pk PRIMARY KEY CLUSTERED (col ASC)": sqlglot moves the
        # columns out of PrimaryKey into a ClusteredColumnConstraint with Ordered nodes.
        if constraint.find(exp.PrimaryKeyColumnConstraint) is not None:
            names.update(ordered.this.name for ordered in constraint.find_all(exp.Ordered))
    return names


def _collect_unique_constraints(
    schema_expr: exp.Schema,
) -> tuple[set[str], list[tuple[str, ...]]]:
    single: set[str] = set()
    composite: list[tuple[str, ...]] = []
    for item in schema_expr.find_all(exp.UniqueColumnConstraint):
        # Inline column-level UNIQUE has no Schema; only table-level constraints count here.
        if isinstance(item.this, exp.Schema):
            names = tuple(column.name for column in item.this.expressions)
            if len(names) == 1:
                single.add(names[0])
            elif names:
                composite.append(names)
    return single, composite


def _extract_column(
    column_def: exp.ColumnDef,
    dialect: SqlDialect,
    primary_key_columns: set[str],
    table_unique_columns: set[str],
) -> Column:
    name = column_def.this.name
    type_str = (
        column_def.args["kind"].sql(dialect=_sqlglot_dialect(dialect))
        if column_def.args.get("kind")
        else ""
    )

    is_primary_key = name in primary_key_columns
    is_not_null = False
    is_unique = name in table_unique_columns
    for constraint in column_def.constraints:
        kind = constraint.kind
        if isinstance(kind, exp.PrimaryKeyColumnConstraint):
            is_primary_key = True
        if isinstance(kind, exp.NotNullColumnConstraint):
            is_not_null = True
        if isinstance(kind, exp.UniqueColumnConstraint):
            is_unique = True

    # A primary key column is implicitly NOT NULL, even when sqlglot doesn't
    # surface a separate NotNullColumnConstraint for it (e.g. `id SERIAL PRIMARY KEY`).
    nullable = not (is_not_null or is_primary_key)

    return Column(
        name=name, type=type_str, nullable=nullable, primary_key=is_primary_key, unique=is_unique
    )


def _apply_alter_statements(
    statements: list[exp.Expression | None], tables: list[Table], dialect: SqlDialect
) -> None:
    """Merge ALTER TABLE ADD COLUMN / ADD PRIMARY KEY / ADD UNIQUE into CREATE TABLE tables."""
    tables_by_name = {table.name: table for table in tables}
    for statement in statements:
        if not isinstance(statement, _ALTER_NODE_TYPES):
            continue
        table = tables_by_name.get(_qualified_name(statement.this))
        if table is None:
            continue
        for action in statement.args.get("actions") or []:
            for column_def in action.find_all(exp.ColumnDef):
                if table.find_column(column_def.this.name) is None:
                    table.columns.append(_extract_column(column_def, dialect, set(), set()))
            for primary_key in action.find_all(exp.PrimaryKey):
                for column in primary_key.expressions:
                    _replace_column(table, column.name, primary_key=True, nullable=False)
            for unique in action.find_all(exp.UniqueColumnConstraint):
                if not isinstance(unique.this, exp.Schema):
                    continue
                names = tuple(column.name for column in unique.this.expressions)
                if len(names) == 1:
                    _replace_column(table, names[0], unique=True)
                elif names:
                    table.unique_constraints.append(names)


def _replace_column(table: Table, name: str, **changes: bool) -> None:
    column = table.find_column(name)
    if column is None:
        return
    index = table.columns.index(column)
    table.columns[index] = replace(column, **changes)


def _extract_foreign_keys(
    statements: list[exp.Expression | None], tables: list[Table]
) -> list[ForeignKeyTuple]:
    tables_by_name = {table.name: table for table in tables}
    results: list[ForeignKeyTuple] = []

    for statement in statements:
        if isinstance(statement, exp.Create) and statement.args.get("kind") == "TABLE":
            results.extend(_foreign_keys_from_create(statement, tables_by_name))
        elif isinstance(statement, _ALTER_NODE_TYPES):
            results.extend(_foreign_keys_from_alter(statement, tables_by_name))

    return list(dict.fromkeys(results))


def _foreign_keys_from_create(
    create_stmt: exp.Create, tables_by_name: dict[str, Table]
) -> list[ForeignKeyTuple]:
    results: list[ForeignKeyTuple] = []
    from_table = _qualified_name(create_stmt.this.this)

    # find_all covers named constraints (CONSTRAINT fk_x FOREIGN KEY ...), which sqlglot
    # wraps in exp.Constraint, as well as plain table-level FOREIGN KEY clauses.
    for foreign_key in create_stmt.this.find_all(exp.ForeignKey):
        results.extend(
            _resolve_foreign_key(
                from_table,
                [column.name for column in foreign_key.expressions],
                foreign_key.args["reference"],
                tables_by_name,
            )
        )
    for column_def in create_stmt.this.find_all(exp.ColumnDef):
        for constraint in column_def.constraints:
            if isinstance(constraint.kind, exp.Reference):
                results.extend(
                    _resolve_foreign_key(
                        from_table,
                        [column_def.this.name],
                        constraint.kind,
                        tables_by_name,
                    )
                )
    return results


def _foreign_keys_from_alter(
    alter_stmt: exp.Alter, tables_by_name: dict[str, Table]
) -> list[ForeignKeyTuple]:
    """Extract FKs added via ALTER TABLE, including inline REFERENCES on ADD COLUMN."""
    results: list[ForeignKeyTuple] = []
    from_table = _qualified_name(alter_stmt.this)

    for action in alter_stmt.args.get("actions") or []:
        for fk in action.find_all(exp.ForeignKey):
            results.extend(
                _resolve_foreign_key(
                    from_table,
                    [column.name for column in fk.expressions],
                    fk.args["reference"],
                    tables_by_name,
                )
            )
        for column_def in action.find_all(exp.ColumnDef):
            for constraint in column_def.constraints:
                if isinstance(constraint.kind, exp.Reference):
                    results.extend(
                        _resolve_foreign_key(
                            from_table,
                            [column_def.this.name],
                            constraint.kind,
                            tables_by_name,
                        )
                    )
    return results


def _resolve_foreign_key(
    from_table: str,
    from_columns: list[str],
    reference: exp.Reference,
    tables_by_name: dict[str, Table],
) -> list[ForeignKeyTuple]:
    target = reference.this
    if isinstance(target, exp.Schema):
        target_table_expr = target.this
        to_columns = [column.name for column in target.expressions]
    else:
        target_table_expr = target
        to_columns = []
    to_table = _qualified_name(target_table_expr)

    target_table = tables_by_name.get(to_table)
    if target_table is None and "." not in to_table:
        # An unqualified reference may point at a schema-qualified table.
        matches = [table for name, table in tables_by_name.items() if name.endswith(f".{to_table}")]
        if len(matches) > 1:
            return []  # ambiguous across schemas: drop rather than point at the wrong table
        if matches:
            target_table = matches[0]
            to_table = target_table.name

    if not to_columns:
        to_columns = _single_primary_key_columns(target_table)
        if not to_columns:
            return []

    if len(from_columns) != len(to_columns):
        raise ValueError(
            f"FOREIGN KEY ({', '.join(from_columns)}) on table '{from_table}' references "
            f"{len(to_columns)} column(s) on '{to_table}' but provides {len(from_columns)}"
        )

    return [
        (from_table, from_column, to_table, to_column)
        for from_column, to_column in zip(from_columns, to_columns, strict=True)
    ]


def _single_primary_key_columns(table: Table | None) -> list[str]:
    if table is None:
        return []
    return [column.name for column in table.columns if column.primary_key]
