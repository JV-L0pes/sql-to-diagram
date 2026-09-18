import sqlglot
from sqlglot import exp

from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.table import Column, Table

# sqlglot names its T-SQL dialect "tsql", not "mssql" — translate our domain
# dialect names to sqlglot's own before handing them to sqlglot's parser.
_SQLGLOT_DIALECT_NAMES = {SqlDialect.MSSQL: "tsql"}


def _sqlglot_dialect(dialect: SqlDialect) -> str:
    return _SQLGLOT_DIALECT_NAMES.get(dialect, dialect.value)


def extract_tables(sql: str, dialect: SqlDialect) -> list[Table]:
    """Parse SQL text and extract Table/Column domain objects for each CREATE TABLE statement."""
    statements = sqlglot.parse(sql, read=_sqlglot_dialect(dialect))
    tables: list[Table] = []

    for statement in statements:
        if statement is None:
            continue
        if not isinstance(statement, exp.Create) or statement.args.get("kind") != "TABLE":
            continue
        tables.append(_extract_table(statement, dialect))

    return tables


def _extract_table(create_stmt: exp.Create, dialect: SqlDialect) -> Table:
    schema_expr = create_stmt.this
    table_name = schema_expr.this.name

    column_defs = [item for item in schema_expr.expressions if isinstance(item, exp.ColumnDef)]

    composite_pk_columns: set[str] = set()
    for item in schema_expr.expressions:
        if isinstance(item, exp.PrimaryKey):
            for pk_col in item.expressions:
                composite_pk_columns.add(pk_col.name)

    columns = [
        _extract_column(column_def, dialect, composite_pk_columns)
        for column_def in column_defs
    ]

    return Table(name=table_name, columns=columns)


def _extract_column(
    column_def: exp.ColumnDef, dialect: SqlDialect, composite_pk_columns: set[str]
) -> Column:
    name = column_def.this.name
    type_str = (
        column_def.args["kind"].sql(dialect=_sqlglot_dialect(dialect))
        if column_def.args.get("kind")
        else ""
    )

    is_primary_key = name in composite_pk_columns
    is_not_null = False
    for constraint in column_def.constraints:
        kind = constraint.kind
        if isinstance(kind, exp.PrimaryKeyColumnConstraint):
            is_primary_key = True
        if isinstance(kind, exp.NotNullColumnConstraint):
            is_not_null = True

    # A primary key column is implicitly NOT NULL, even when sqlglot doesn't
    # surface a separate NotNullColumnConstraint for it (e.g. `id SERIAL PRIMARY KEY`).
    nullable = not (is_not_null or is_primary_key)

    return Column(name=name, type=type_str, nullable=nullable, primary_key=is_primary_key)


def extract_foreign_keys(sql: str, dialect: SqlDialect) -> list[tuple[str, str, str, str]]:
    """Parse SQL text and extract explicit table-level FOREIGN KEY constraints.

    Returns one (from_table, from_column, to_table, to_column) tuple per FK
    column pair, in source order.
    """
    statements = sqlglot.parse(sql, read=_sqlglot_dialect(dialect))
    results: list[tuple[str, str, str, str]] = []

    for statement in statements:
        if statement is None:
            continue
        if not isinstance(statement, exp.Create) or statement.args.get("kind") != "TABLE":
            continue
        schema_expr = statement.this
        from_table = schema_expr.this.name

        for item in schema_expr.expressions:
            if isinstance(item, exp.ForeignKey):
                from_columns = [c.name for c in item.expressions]
                reference = item.args["reference"]
                to_table = reference.this.this.name
                to_columns = [c.name for c in reference.this.expressions]
                for from_col, to_col in zip(from_columns, to_columns):
                    results.append((from_table, from_col, to_table, to_col))
            elif isinstance(item, exp.ColumnDef):
                from_column = item.this.name
                for constraint in item.constraints:
                    if isinstance(constraint.kind, exp.Reference):
                        reference_schema = constraint.kind.this
                        to_table = reference_schema.this.name
                        to_column = reference_schema.expressions[0].name
                        results.append((from_table, from_column, to_table, to_column))

    return results
