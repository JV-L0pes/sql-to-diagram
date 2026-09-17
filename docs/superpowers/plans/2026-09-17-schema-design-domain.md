# Schema Design Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the (already-deleted) legacy regex SQL parser with a real, multi-dialect parsing engine in `apps/api`'s `schema_design` bounded context, exposed as `POST /api/schema/parse`, that extracts tables/columns/relationships and surfaces structural modeling warnings.

**Architecture:** Four-layer DDD split inside `apps/api/src/schema_design/`: `domain/` (pure value objects: `Table`, `Column`, `Relationship`, `SchemaWarning`, `ParsedSchema`, plus the existing `SqlDialect`), `infrastructure/` (sqlglot-based parsing + relationship/warning detection — the only layer that imports sqlglot), `application/` (the `ParseSqlSchema` use case orchestrating domain + infrastructure), `interfaces/` (FastAPI router + Pydantic schemas). No feature UI — verified via pytest and FastAPI's `/docs`.

**Tech Stack:** sqlglot (multi-dialect SQL parser), Python dataclasses for domain objects, FastAPI + Pydantic for the HTTP boundary, pytest for tests (all layers).

**Spec:** [docs/superpowers/specs/2026-09-17-schema-design-domain.md](../specs/2026-09-17-schema-design-domain.md)

## Global Constraints

- `domain/` files import nothing from `sqlglot`, `fastapi`, or `sqlalchemy` — verified by grep in each task's self-review.
- No bare `except`/silent fallback anywhere — a parse failure must propagate as a typed exception, never a silently-empty result.
- Endpoint is public — no auth dependency, no `get_db` dependency (this feature never touches the database).
- Dialect values are exactly `SqlDialect`'s four members: `postgres`, `mysql`, `sqlite`, `mssql` (already defined in `apps/api/src/schema_design/domain/dialect.py` from Phase 1 — do not redefine).
- Relationship `source` is exactly `"explicit"` or `"inferred"` (spec's API Contract section) — these are the only two values, used consistently across every task.

---

## File Structure

```
apps/api/
├── pyproject.toml                          # add sqlglot dependency (Task 1)
└── src/schema_design/
    ├── domain/
    │   ├── dialect.py                      # existing (Phase 1) — untouched
    │   ├── table.py                        # Column, Table (Task 1)
    │   ├── relationship.py                 # RelationshipType, RelationshipSource, Relationship (Task 2)
    │   ├── warning.py                      # WarningCode, SchemaWarning (Task 2)
    │   └── parsed_schema.py                # ParsedSchema aggregate (Task 2)
    ├── infrastructure/
    │   ├── sqlglot_parser.py               # SQL text -> list[Table] (Tasks 3-5)
    │   ├── relationship_detector.py        # list[Table] + raw constraint data -> list[Relationship] (Tasks 6-7)
    │   └── structural_validator.py         # ParsedSchema -> list[SchemaWarning] (Task 8)
    ├── application/
    │   └── parse_sql_schema.py             # ParseSqlSchema use case (Task 9)
    └── interfaces/
        ├── schemas.py                      # Pydantic request/response models (Task 10)
        └── router.py                       # POST /api/schema/parse (Task 10)
apps/api/tests/schema_design/
├── test_dialect.py                         # existing (Phase 1) — untouched
├── test_table.py                           # Task 1
├── test_relationship.py                    # Task 2
├── test_warning.py                         # Task 2
├── test_sqlglot_parser.py                  # Tasks 3-5
├── test_relationship_detector.py           # Tasks 6-7
├── test_structural_validator.py            # Task 8
├── test_parse_sql_schema.py                # Task 9
└── test_parse_endpoint.py                  # Task 10-11
```

---

### Task 1: Domain — `Table`/`Column`, plus the sqlglot dependency

**Files:**
- Modify: `apps/api/pyproject.toml` (add `sqlglot` to `dependencies`)
- Create: `apps/api/src/schema_design/domain/table.py`
- Test: `apps/api/tests/schema_design/test_table.py`

**Interfaces:**
- Produces: `Column` (dataclass: `name: str`, `type: str`, `nullable: bool`, `primary_key: bool`), `Table` (dataclass: `name: str`, `columns: list[Column]`, with a `find_column(name: str) -> Column | None` helper method).

- [ ] **Step 1: Add sqlglot to `apps/api/pyproject.toml`**

In the `[project]` section's `dependencies` list, add (alphabetically, alongside the existing entries):
```toml
    "sqlglot>=25.0.0",
```

- [ ] **Step 2: Install it**

Run (from `apps/api`, using its venv): `pip install -e ".[dev]"`
Expected: installs `sqlglot` with no errors.

- [ ] **Step 3: Write the failing test — `apps/api/tests/schema_design/test_table.py`**

```python
from src.schema_design.domain.table import Column, Table


def test_table_find_column_returns_matching_column():
    id_col = Column(name="id", type="INTEGER", nullable=False, primary_key=True)
    email_col = Column(name="email", type="VARCHAR(255)", nullable=False, primary_key=False)
    table = Table(name="users", columns=[id_col, email_col])

    assert table.find_column("email") is email_col


def test_table_find_column_returns_none_when_missing():
    table = Table(name="users", columns=[])

    assert table.find_column("missing") is None
```

- [ ] **Step 4: Run it to verify it fails**

Run: `pytest tests/schema_design/test_table.py -v` (from `apps/api`)
Expected: FAIL — `ModuleNotFoundError: No module named 'src.schema_design.domain.table'`

- [ ] **Step 5: Implement `apps/api/src/schema_design/domain/table.py`**

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    nullable: bool
    primary_key: bool


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)

    def find_column(self, name: str) -> Column | None:
        for column in self.columns:
            if column.name == name:
                return column
        return None
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `pytest tests/schema_design/test_table.py -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add apps/api/pyproject.toml apps/api/src/schema_design/domain/table.py apps/api/tests/schema_design/test_table.py
git commit -m "feat(api): add sqlglot dependency and Table/Column domain objects"
```

---

### Task 2: Domain — `Relationship`, `SchemaWarning`, `ParsedSchema`

**Files:**
- Create: `apps/api/src/schema_design/domain/relationship.py`
- Create: `apps/api/src/schema_design/domain/warning.py`
- Create: `apps/api/src/schema_design/domain/parsed_schema.py`
- Test: `apps/api/tests/schema_design/test_relationship.py`
- Test: `apps/api/tests/schema_design/test_warning.py`

**Interfaces:**
- Consumes: `Table`, `Column` from `apps/api/src/schema_design/domain/table.py` (Task 1).
- Produces: `RelationshipType` (str enum: `ONE_TO_ONE`, `ONE_TO_MANY`, `MANY_TO_ONE`, `MANY_TO_MANY`), `RelationshipSource` (str enum: `EXPLICIT` = `"explicit"`, `INFERRED` = `"inferred"`), `Relationship` (dataclass: `from_table: str`, `from_column: str`, `to_table: str`, `to_column: str`, `type: RelationshipType`, `source: RelationshipSource`). `WarningCode` (str enum: `MISSING_PRIMARY_KEY` = `"missing_primary_key"`, `NON_ATOMIC_COLUMN_TYPE` = `"non_atomic_column_type"`, `NULLABLE_FOREIGN_KEY` = `"nullable_foreign_key"`, `NON_SNAKE_CASE_IDENTIFIER` = `"non_snake_case_identifier"`), `SchemaWarning` (dataclass: `code: WarningCode`, `table: str`, `message: str`). `ParsedSchema` (dataclass: `tables: list[Table]`, `relationships: list[Relationship]`, `warnings: list[SchemaWarning]`).

- [ ] **Step 1: Write the failing tests — `apps/api/tests/schema_design/test_relationship.py`**

```python
from src.schema_design.domain.relationship import Relationship, RelationshipSource, RelationshipType


def test_relationship_source_values_match_api_contract():
    assert RelationshipSource.EXPLICIT.value == "explicit"
    assert RelationshipSource.INFERRED.value == "inferred"


def test_relationship_holds_all_fields():
    rel = Relationship(
        from_table="posts",
        from_column="user_id",
        to_table="users",
        to_column="id",
        type=RelationshipType.MANY_TO_ONE,
        source=RelationshipSource.EXPLICIT,
    )

    assert rel.from_table == "posts"
    assert rel.to_table == "users"
    assert rel.type == RelationshipType.MANY_TO_ONE
    assert rel.source == RelationshipSource.EXPLICIT
```

- [ ] **Step 2: Write the failing tests — `apps/api/tests/schema_design/test_warning.py`**

```python
from src.schema_design.domain.warning import SchemaWarning, WarningCode


def test_warning_codes_match_api_contract():
    assert WarningCode.MISSING_PRIMARY_KEY.value == "missing_primary_key"
    assert WarningCode.NON_ATOMIC_COLUMN_TYPE.value == "non_atomic_column_type"
    assert WarningCode.NULLABLE_FOREIGN_KEY.value == "nullable_foreign_key"
    assert WarningCode.NON_SNAKE_CASE_IDENTIFIER.value == "non_snake_case_identifier"


def test_warning_holds_all_fields():
    warning = SchemaWarning(
        code=WarningCode.MISSING_PRIMARY_KEY,
        table="logs",
        message="Table 'logs' has no primary key.",
    )

    assert warning.code == WarningCode.MISSING_PRIMARY_KEY
    assert warning.table == "logs"
```

- [ ] **Step 3: Run both to verify they fail**

Run: `pytest tests/schema_design/test_relationship.py tests/schema_design/test_warning.py -v`
Expected: FAIL — modules don't exist yet.

- [ ] **Step 4: Implement `apps/api/src/schema_design/domain/relationship.py`**

```python
from dataclasses import dataclass
from enum import Enum


class RelationshipType(str, Enum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class RelationshipSource(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"


@dataclass(frozen=True)
class Relationship:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    type: RelationshipType
    source: RelationshipSource
```

- [ ] **Step 5: Implement `apps/api/src/schema_design/domain/warning.py`**

```python
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
```

- [ ] **Step 6: Implement `apps/api/src/schema_design/domain/parsed_schema.py`**

```python
from dataclasses import dataclass, field

from src.schema_design.domain.relationship import Relationship
from src.schema_design.domain.table import Table
from src.schema_design.domain.warning import SchemaWarning


@dataclass
class ParsedSchema:
    tables: list[Table] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    warnings: list[SchemaWarning] = field(default_factory=list)
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pytest tests/schema_design/test_relationship.py tests/schema_design/test_warning.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Verify no framework imports leaked into domain**

Run: `grep -rn "^import\|^from" apps/api/src/schema_design/domain/`
Expected: only stdlib (`dataclasses`, `enum`) and intra-domain imports — no `sqlglot`, `fastapi`, `sqlalchemy`.

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/schema_design/domain/relationship.py apps/api/src/schema_design/domain/warning.py apps/api/src/schema_design/domain/parsed_schema.py apps/api/tests/schema_design/test_relationship.py apps/api/tests/schema_design/test_warning.py
git commit -m "feat(api): add Relationship, SchemaWarning, and ParsedSchema domain objects"
```

---

### Task 3: Infrastructure — sqlglot table/column extraction (Postgres)

**Files:**
- Create: `apps/api/src/schema_design/infrastructure/sqlglot_parser.py`
- Test: `apps/api/tests/schema_design/test_sqlglot_parser.py`

**Interfaces:**
- Consumes: `Table`, `Column` (Task 1), `SqlDialect` (Phase 1, `apps/api/src/schema_design/domain/dialect.py`).
- Produces: `extract_tables(sql: str, dialect: SqlDialect) -> list[Table]` in `sqlglot_parser.py`. Also produces (for Task 4's use, but implemented here since it comes from the same AST walk): a private helper the module uses internally — later tasks import only `extract_tables`, plus the two functions Task 4 adds to this same file.

**Before you write extraction code:** sqlglot's exact AST node names/attributes for `CREATE TABLE` can vary by version. Do NOT guess from memory — inspect the real output first:

```bash
python3 -c "
import sqlglot
from sqlglot import exp
sql = '''CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL,
  bio TEXT
);'''
stmt = sqlglot.parse_one(sql, read='postgres')
print(repr(stmt))
print('---')
for node in stmt.walk():
    print(type(node[0]).__name__, getattr(node[0], 'args', None))
"
```
Run this (from `apps/api`, with the venv active) and read the output before writing extraction code. Identify: (a) the node type for a `CREATE TABLE` statement and how to get the table name, (b) the node type for each column definition and how to get its name/type-as-string/nullability, (c) how a column-level `PRIMARY KEY` and a table-level `PRIMARY KEY (...)` constraint both surface in the tree, since both must set `Column.primary_key = True`.

- [ ] **Step 1: Run the exploration script above and note the node types/attributes you find**

(No test yet — this is discovery. Keep your notes; you'll need them for Step 3.)

- [ ] **Step 2: Write the failing test — `apps/api/tests/schema_design/test_sqlglot_parser.py`**

```python
from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.infrastructure.sqlglot_parser import extract_tables


def test_extract_tables_reads_columns_and_column_level_primary_key():
    sql = """
    CREATE TABLE users (
      id SERIAL PRIMARY KEY,
      email VARCHAR(255) NOT NULL,
      bio TEXT
    );
    """

    tables = extract_tables(sql, SqlDialect.POSTGRES)

    assert len(tables) == 1
    users = tables[0]
    assert users.name == "users"
    assert len(users.columns) == 3

    id_col = users.find_column("id")
    assert id_col.primary_key is True
    assert id_col.nullable is False

    email_col = users.find_column("email")
    assert email_col.primary_key is False
    assert email_col.nullable is False

    bio_col = users.find_column("bio")
    assert bio_col.nullable is True
    assert bio_col.primary_key is False


def test_extract_tables_reads_table_level_composite_primary_key():
    sql = """
    CREATE TABLE order_items (
      order_id INTEGER NOT NULL,
      product_id INTEGER NOT NULL,
      quantity INTEGER NOT NULL,
      PRIMARY KEY (order_id, product_id)
    );
    """

    tables = extract_tables(sql, SqlDialect.POSTGRES)

    order_items = tables[0]
    assert order_items.find_column("order_id").primary_key is True
    assert order_items.find_column("product_id").primary_key is True
    assert order_items.find_column("quantity").primary_key is False


def test_extract_tables_handles_multiple_statements():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL);
    """

    tables = extract_tables(sql, SqlDialect.POSTGRES)

    assert [t.name for t in tables] == ["users", "posts"]
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/schema_design/test_sqlglot_parser.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 4: Implement `apps/api/src/schema_design/infrastructure/sqlglot_parser.py`**

Using what you found in Step 1's exploration, implement `extract_tables`. The shape below is the expected structure — fill in the exact sqlglot attribute access based on your exploration output (sqlglot's `CREATE TABLE` statement is an `exp.Create` whose `.this` is an `exp.Schema` containing an `exp.Table` and a list of column/constraint expressions; column definitions are `exp.ColumnDef` nodes; a table-level primary key is an `exp.PrimaryKey` node; `NOT NULL` and column-level `PRIMARY KEY` appear as constraint objects attached to a `ColumnDef` — confirm the exact class names from your Step 1 output before writing the `isinstance` checks):

```python
import sqlglot
from sqlglot import exp

from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.table import Column, Table


def extract_tables(sql: str, dialect: SqlDialect) -> list[Table]:
    statements = sqlglot.parse(sql, read=dialect.value)
    tables: list[Table] = []

    for statement in statements:
        if not isinstance(statement, exp.Create) or statement.args.get("kind") != "TABLE":
            continue
        tables.append(_extract_table(statement, dialect))

    return tables


def _extract_table(create_stmt: exp.Create, dialect: SqlDialect) -> Table:
    schema_expr = create_stmt.this
    table_name = schema_expr.this.name

    columns: list[Column] = []
    composite_pk_columns: set[str] = set()

    for item in schema_expr.expressions:
        if isinstance(item, exp.ColumnDef):
            columns.append(_extract_column(item, dialect))
        elif isinstance(item, exp.PrimaryKey):
            for pk_col in item.expressions:
                composite_pk_columns.add(pk_col.name)

    for column in columns:
        if column.name in composite_pk_columns:
            object.__setattr__(column, "primary_key", True)

    return Table(name=table_name, columns=columns)


def _extract_column(column_def: exp.ColumnDef, dialect: SqlDialect) -> Column:
    name = column_def.this.name
    type_str = column_def.args["kind"].sql(dialect=dialect.value) if column_def.args.get("kind") else ""

    is_primary_key = False
    is_not_null = False
    for constraint in column_def.constraints:
        kind = constraint.kind
        if isinstance(kind, exp.PrimaryKeyColumnConstraint):
            is_primary_key = True
        if isinstance(kind, exp.NotNullColumnConstraint):
            is_not_null = True

    return Column(name=name, type=type_str, nullable=not is_not_null, primary_key=is_primary_key)
```

Adjust the `isinstance` checks and attribute names to match what your Step 1 exploration actually showed — the sqlglot version pinned in `pyproject.toml` is the ground truth, not this snippet.

- [ ] **Step 5: Run the tests, iterate until they pass**

Run: `pytest tests/schema_design/test_sqlglot_parser.py -v`
If a test fails, re-run the exploration script from the top of this task with the SPECIFIC failing SQL to see what sqlglot actually produced, then adjust `_extract_column`/`_extract_table`. Do not guess a second time — inspect again.
Expected once passing: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/schema_design/infrastructure/sqlglot_parser.py apps/api/tests/schema_design/test_sqlglot_parser.py
git commit -m "feat(api): extract tables/columns from Postgres CREATE TABLE via sqlglot"
```

---

### Task 4: Infrastructure — explicit foreign key extraction

**Files:**
- Modify: `apps/api/src/schema_design/infrastructure/sqlglot_parser.py`
- Test: `apps/api/tests/schema_design/test_sqlglot_parser.py` (add to existing file)

**Interfaces:**
- Consumes: `Table` (Task 1), the AST-walking helpers already in `sqlglot_parser.py` (Task 3).
- Produces: `extract_foreign_keys(sql: str, dialect: SqlDialect) -> list[tuple[str, str, str, str]]` in `sqlglot_parser.py`, where each tuple is `(from_table, from_column, to_table, to_column)` — one tuple per FK column pair, in source order. This raw form (not yet a `Relationship`) is what Task 6's relationship detector consumes to decide cardinality and build `Relationship` objects.

- [ ] **Step 1: Explore sqlglot's `FOREIGN KEY` AST shape**

```bash
python3 -c "
import sqlglot
from sqlglot import exp
sql = '''CREATE TABLE posts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id)
);'''
stmt = sqlglot.parse_one(sql, read='postgres')
for node in stmt.walk():
    print(type(node[0]).__name__)
print(repr(stmt.find(exp.ForeignKey)))
"
```
Note the node type (`exp.ForeignKey`) and how to reach the referenced table/columns (typically via a `Reference` child holding another `Schema`/`Table`).

- [ ] **Step 2: Write the failing test — append to `apps/api/tests/schema_design/test_sqlglot_parser.py`**

```python
from src.schema_design.infrastructure.sqlglot_parser import extract_foreign_keys


def test_extract_foreign_keys_from_table_level_constraint():
    sql = """
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    foreign_keys = extract_foreign_keys(sql, SqlDialect.POSTGRES)

    assert foreign_keys == [("posts", "user_id", "users", "id")]


def test_extract_foreign_keys_returns_empty_list_when_none_declared():
    sql = "CREATE TABLE users (id SERIAL PRIMARY KEY);"

    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == []
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/schema_design/test_sqlglot_parser.py -v -k foreign_key`
Expected: FAIL — `extract_foreign_keys` not defined.

- [ ] **Step 4: Implement `extract_foreign_keys` in `sqlglot_parser.py`**

Append to the file (using your Step 1 findings to fix the exact attribute path to the referenced table/column):

```python
def extract_foreign_keys(sql: str, dialect: SqlDialect) -> list[tuple[str, str, str, str]]:
    statements = sqlglot.parse(sql, read=dialect.value)
    results: list[tuple[str, str, str, str]] = []

    for statement in statements:
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

    return results
```

Adjust `reference.this.this.name` / `reference.this.expressions` to match the actual attribute chain from your Step 1 exploration.

- [ ] **Step 5: Run the tests, iterate until they pass**

Run: `pytest tests/schema_design/test_sqlglot_parser.py -v`
Expected: PASS (5 tests total in this file)

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/schema_design/infrastructure/sqlglot_parser.py apps/api/tests/schema_design/test_sqlglot_parser.py
git commit -m "feat(api): extract explicit foreign keys via sqlglot"
```

---

### Task 5: Infrastructure — multi-dialect parametrized coverage

**Files:**
- Modify: `apps/api/tests/schema_design/test_sqlglot_parser.py` (add parametrized test)
- Modify: `apps/api/src/schema_design/infrastructure/sqlglot_parser.py` (only if a dialect-specific fix is needed — see Step 3)

**Interfaces:**
- Consumes: `extract_tables` (Task 3), `SqlDialect` (Phase 1).
- Produces: nothing new — this task is a coverage/regression task proving Tasks 3-4's implementation generalizes.

- [ ] **Step 1: Write the parametrized test — append to `apps/api/tests/schema_design/test_sqlglot_parser.py`**

```python
import pytest


DIALECT_CREATE_TABLE = {
    SqlDialect.POSTGRES: "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL);",
    SqlDialect.MYSQL: "CREATE TABLE users (id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(255) NOT NULL);",
    SqlDialect.SQLITE: "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL);",
    SqlDialect.MSSQL: "CREATE TABLE users (id INT IDENTITY(1,1) PRIMARY KEY, email VARCHAR(255) NOT NULL);",
}


@pytest.mark.parametrize("dialect", list(SqlDialect))
def test_extract_tables_works_across_all_dialects(dialect):
    sql = DIALECT_CREATE_TABLE[dialect]

    tables = extract_tables(sql, dialect)

    assert len(tables) == 1
    users = tables[0]
    assert users.name == "users"
    id_col = users.find_column("id")
    assert id_col.primary_key is True
    email_col = users.find_column("email")
    assert email_col.nullable is False
```

- [ ] **Step 2: Run it**

Run: `pytest tests/schema_design/test_sqlglot_parser.py -v -k all_dialects`
Expected: likely FAIL for at least one dialect on the first attempt — dialect-specific syntax (`AUTO_INCREMENT`, `IDENTITY(1,1)`) may surface PK/type info differently in sqlglot's AST than Postgres's `SERIAL`.

- [ ] **Step 3: For each failing dialect, inspect and fix**

For any failing dialect, run the same exploration pattern from Task 3/4 with that dialect's SQL and `read="<dialect>"` to see what sqlglot actually produced, then adjust `_extract_column`/`_extract_table` in `sqlglot_parser.py` to handle the difference (e.g., MySQL's `AUTO_INCREMENT` may appear as a separate constraint type than Postgres's column-level `PRIMARY KEY` — both must still set `primary_key=True` on that column). Do not special-case by `if dialect == X` unless the underlying AST genuinely differs — prefer handling by AST node type, which is usually dialect-agnostic in sqlglot's normalized tree.

- [ ] **Step 4: Run all schema_design tests to confirm nothing regressed**

Run: `pytest tests/schema_design/ -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/schema_design/infrastructure/sqlglot_parser.py apps/api/tests/schema_design/test_sqlglot_parser.py
git commit -m "test(api): verify table extraction works across all four dialects"
```

---

### Task 6: Infrastructure — relationship detection (explicit + junction/many-to-many)

**Files:**
- Create: `apps/api/src/schema_design/infrastructure/relationship_detector.py`
- Test: `apps/api/tests/schema_design/test_relationship_detector.py`

**Interfaces:**
- Consumes: `Table`, `Column` (Task 1), `Relationship`, `RelationshipType`, `RelationshipSource` (Task 2), the `(from_table, from_column, to_table, to_column)` tuple shape from `extract_foreign_keys` (Task 4).
- Produces: `detect_explicit_relationships(tables: list[Table], foreign_keys: list[tuple[str, str, str, str]]) -> list[Relationship]` — handles both direct FK relationships (with cardinality via uniqueness) and junction-table many-to-many collapsing. This is the ONLY function later tasks call for explicit-relationship detection; Task 7 adds a second function (`detect_inferred_relationships`) to this same file.

- [ ] **Step 1: Write the failing tests — `apps/api/tests/schema_design/test_relationship_detector.py`**

```python
from src.schema_design.domain.relationship import RelationshipSource, RelationshipType
from src.schema_design.domain.table import Column, Table
from src.schema_design.infrastructure.relationship_detector import detect_explicit_relationships


def _table(name, columns):
    return Table(name=name, columns=columns)


def test_detects_many_to_one_for_simple_foreign_key():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )
    foreign_keys = [("posts", "user_id", "users", "id")]

    relationships = detect_explicit_relationships([users, posts], foreign_keys)

    assert len(relationships) == 1
    rel = relationships[0]
    assert rel.from_table == "posts"
    assert rel.to_table == "users"
    assert rel.type == RelationshipType.MANY_TO_ONE
    assert rel.source == RelationshipSource.EXPLICIT


def test_detects_one_to_one_when_both_sides_unique():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    profiles = _table(
        "profiles",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, True),  # PK on this table too -> unique
        ],
    )
    foreign_keys = [("profiles", "user_id", "users", "id")]

    relationships = detect_explicit_relationships([users, profiles], foreign_keys)

    assert relationships[0].type == RelationshipType.ONE_TO_ONE


def test_collapses_junction_table_into_many_to_many():
    students = _table("students", [Column("id", "INTEGER", False, True)])
    courses = _table("courses", [Column("id", "INTEGER", False, True)])
    enrollments = _table(
        "enrollments",
        [
            Column("student_id", "INTEGER", False, True),
            Column("course_id", "INTEGER", False, True),
        ],
    )
    foreign_keys = [
        ("enrollments", "student_id", "students", "id"),
        ("enrollments", "course_id", "courses", "id"),
    ]

    relationships = detect_explicit_relationships([students, courses, enrollments], foreign_keys)

    many_to_many = [r for r in relationships if r.type == RelationshipType.MANY_TO_MANY]
    assert len(many_to_many) == 2  # both directions
    pairs = {(r.from_table, r.to_table) for r in many_to_many}
    assert pairs == {("students", "courses"), ("courses", "students")}
    # The junction table itself should not appear as a plain FK relationship
    assert all(r.from_table != "enrollments" for r in relationships)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/schema_design/test_relationship_detector.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/schema_design/infrastructure/relationship_detector.py`**

```python
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
        rel_type = _determine_cardinality(tables_by_name, from_table, from_column, to_table, to_column)
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
            Relationship(table_a, col_a, table_b, col_b, RelationshipType.MANY_TO_MANY, RelationshipSource.EXPLICIT)
        )
        relationships.append(
            Relationship(table_b, col_b, table_a, col_a, RelationshipType.MANY_TO_MANY, RelationshipSource.EXPLICIT)
        )

    return relationships


def _identify_junction_tables(tables: list[Table], foreign_keys: list[tuple[str, str, str, str]]) -> set[str]:
    junction_tables: set[str] = set()

    for table in tables:
        fks_from_this_table = [fk for fk in foreign_keys if fk[0] == table.name]
        if len(fks_from_this_table) != 2:
            continue

        fk_columns = {fk[1] for fk in fks_from_this_table}
        pk_columns = {c.name for c in table.columns if c.primary_key}
        non_fk_non_pk_columns = [c for c in table.columns if c.name not in fk_columns]

        if pk_columns == fk_columns and len(non_fk_non_pk_columns) <= 2:
            junction_tables.add(table.name)

    return junction_tables


def _is_column_unique(table: Table, column_name: str) -> bool:
    column = table.find_column(column_name)
    return column is not None and column.primary_key


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
```

Note: `_is_column_unique` only checks `primary_key` for now (no separate `UNIQUE` constraint tracking exists on `Column` yet — that's acceptable for this task's scope per the spec, which only requires PK-based uniqueness for cardinality; a future phase can extend `Column` with a `unique: bool` field if needed).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/schema_design/test_relationship_detector.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/schema_design/infrastructure/relationship_detector.py apps/api/tests/schema_design/test_relationship_detector.py
git commit -m "feat(api): detect explicit and many-to-many relationships"
```

---

### Task 7: Infrastructure — naming-convention relationship inference

**Files:**
- Modify: `apps/api/src/schema_design/infrastructure/relationship_detector.py`
- Test: `apps/api/tests/schema_design/test_relationship_detector.py` (add to existing file)

**Interfaces:**
- Consumes: `Table`, `Column` (Task 1), `Relationship`/`RelationshipSource` (Task 2).
- Produces: `detect_inferred_relationships(tables: list[Table], explicit_relationships: list[Relationship]) -> list[Relationship]` in `relationship_detector.py`.

- [ ] **Step 1: Write the failing tests — append to `apps/api/tests/schema_design/test_relationship_detector.py`**

```python
from src.schema_design.infrastructure.relationship_detector import detect_inferred_relationships


def test_infers_relationship_from_naming_convention_when_no_explicit_fk():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )

    relationships = detect_inferred_relationships([users, posts], explicit_relationships=[])

    assert len(relationships) == 1
    rel = relationships[0]
    assert rel.from_table == "posts"
    assert rel.from_column == "user_id"
    assert rel.to_table == "users"
    assert rel.to_column == "id"
    assert rel.source == RelationshipSource.INFERRED


def test_does_not_infer_when_explicit_relationship_already_covers_the_column():
    from src.schema_design.domain.relationship import Relationship

    users = _table("users", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )
    explicit = [
        Relationship("posts", "user_id", "users", "id", RelationshipType.MANY_TO_ONE, RelationshipSource.EXPLICIT)
    ]

    relationships = detect_inferred_relationships([users, posts], explicit_relationships=explicit)

    assert relationships == []


def test_does_not_infer_when_no_matching_table_exists():
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("category_id", "INTEGER", False, False),
        ],
    )

    relationships = detect_inferred_relationships([posts], explicit_relationships=[])

    assert relationships == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/schema_design/test_relationship_detector.py -v -k infers`
Expected: FAIL — `detect_inferred_relationships` not defined.

- [ ] **Step 3: Implement `detect_inferred_relationships` — append to `relationship_detector.py`**

```python
def detect_inferred_relationships(
    tables: list[Table],
    explicit_relationships: list[Relationship],
) -> list[Relationship]:
    explicit_columns = {(r.from_table, r.from_column) for r in explicit_relationships}
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
            target_id_column = target_table.find_column("id")
            if target_id_column is None:
                continue

            inferred.append(
                Relationship(
                    from_table=table.name,
                    from_column=column.name,
                    to_table=target_table_name,
                    to_column="id",
                    type=RelationshipType.MANY_TO_ONE,
                    source=RelationshipSource.INFERRED,
                )
            )

    return inferred


def _find_matching_table(column_name: str, table_names: list[str], exclude: str) -> str | None:
    prefix = column_name[: -len("_id")].lower()
    candidates = {prefix, f"{prefix}s", f"{prefix}es", f"{prefix}a", f"{prefix}as"}

    for table_name in table_names:
        if table_name == exclude:
            continue
        if table_name.lower() in candidates:
            return table_name

    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/schema_design/test_relationship_detector.py -v`
Expected: PASS (6 tests total in this file)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/schema_design/infrastructure/relationship_detector.py apps/api/tests/schema_design/test_relationship_detector.py
git commit -m "feat(api): infer relationships from column naming convention"
```

---

### Task 8: Infrastructure — structural warnings

**Files:**
- Create: `apps/api/src/schema_design/infrastructure/structural_validator.py`
- Test: `apps/api/tests/schema_design/test_structural_validator.py`

**Interfaces:**
- Consumes: `Table`, `Column` (Task 1), `Relationship` (Task 2), `SchemaWarning`, `WarningCode` (Task 2).
- Produces: `validate_structure(tables: list[Table], relationships: list[Relationship]) -> list[SchemaWarning]` in `structural_validator.py`.

- [ ] **Step 1: Write the failing tests — `apps/api/tests/schema_design/test_structural_validator.py`**

```python
from src.schema_design.domain.relationship import Relationship, RelationshipSource, RelationshipType
from src.schema_design.domain.table import Column, Table
from src.schema_design.domain.warning import WarningCode
from src.schema_design.infrastructure.structural_validator import validate_structure


def test_warns_on_missing_primary_key():
    logs = Table(name="logs", columns=[Column("message", "TEXT", True, False)])

    warnings = validate_structure([logs], [])

    codes = [w.code for w in warnings]
    assert WarningCode.MISSING_PRIMARY_KEY in codes


def test_no_warning_when_primary_key_present():
    users = Table(name="users", columns=[Column("id", "INTEGER", False, True)])

    warnings = validate_structure([users], [])

    assert all(w.code != WarningCode.MISSING_PRIMARY_KEY for w in warnings)


def test_warns_on_non_atomic_column_type():
    tags_table = Table(
        name="posts",
        columns=[
            Column("id", "INTEGER", False, True),
            Column("tags", "TEXT[]", True, False),
        ],
    )

    warnings = validate_structure([tags_table], [])

    codes = [w.code for w in warnings]
    assert WarningCode.NON_ATOMIC_COLUMN_TYPE in codes


def test_warns_on_nullable_foreign_key():
    users = Table(name="users", columns=[Column("id", "INTEGER", False, True)])
    posts = Table(
        name="posts",
        columns=[
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", True, False),  # nullable FK
        ],
    )
    relationships = [
        Relationship("posts", "user_id", "users", "id", RelationshipType.MANY_TO_ONE, RelationshipSource.EXPLICIT)
    ]

    warnings = validate_structure([users, posts], relationships)

    codes = [w.code for w in warnings]
    assert WarningCode.NULLABLE_FOREIGN_KEY in codes


def test_warns_on_non_snake_case_identifier():
    weird = Table(name="UserAccounts", columns=[Column("id", "INTEGER", False, True)])

    warnings = validate_structure([weird], [])

    codes = [w.code for w in warnings]
    assert WarningCode.NON_SNAKE_CASE_IDENTIFIER in codes
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/schema_design/test_structural_validator.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/schema_design/infrastructure/structural_validator.py`**

```python
import re

from src.schema_design.domain.relationship import Relationship
from src.schema_design.domain.table import Table
from src.schema_design.domain.warning import SchemaWarning, WarningCode

_SNAKE_CASE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_NON_ATOMIC_TYPE_MARKERS = ("[]", "ARRAY", "JSON", "JSONB")


def validate_structure(tables: list[Table], relationships: list[Relationship]) -> list[SchemaWarning]:
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
                    message=f"Column '{table.name}.{column.name}' has a non-atomic type ({column.type}).",
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


def _check_nullable_foreign_keys(tables: list[Table], relationships: list[Relationship]) -> list[SchemaWarning]:
    warnings = []
    tables_by_name = {t.name: t for t in tables}

    for rel in relationships:
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/schema_design/test_structural_validator.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/schema_design/infrastructure/structural_validator.py apps/api/tests/schema_design/test_structural_validator.py
git commit -m "feat(api): add structural schema warnings (PK, atomic types, nullable FK, naming)"
```

---

### Task 9: Application — `ParseSqlSchema` use case

**Files:**
- Create: `apps/api/src/schema_design/application/parse_sql_schema.py`
- Test: `apps/api/tests/schema_design/test_parse_sql_schema.py`

**Interfaces:**
- Consumes: `extract_tables`, `extract_foreign_keys` (Task 3-4), `detect_explicit_relationships`, `detect_inferred_relationships` (Tasks 6-7), `validate_structure` (Task 8), `ParsedSchema` (Task 2), `SqlDialect` (Phase 1).
- Produces: `parse_sql_schema(sql: str, dialect: SqlDialect) -> ParsedSchema` — the single entry point Task 10's router calls.

- [ ] **Step 1: Write the failing test — `apps/api/tests/schema_design/test_parse_sql_schema.py`**

```python
from src.schema_design.application.parse_sql_schema import parse_sql_schema
from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.relationship import RelationshipSource


def test_parse_sql_schema_returns_tables_relationships_and_warnings():
    sql = """
    CREATE TABLE users (
      id SERIAL PRIMARY KEY,
      email VARCHAR(255) NOT NULL
    );
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE logs (
      message TEXT
    );
    """

    result = parse_sql_schema(sql, SqlDialect.POSTGRES)

    assert {t.name for t in result.tables} == {"users", "posts", "logs"}
    assert len(result.relationships) == 1
    assert result.relationships[0].source == RelationshipSource.EXPLICIT
    assert any(w.table == "logs" for w in result.warnings)


def test_parse_sql_schema_combines_explicit_and_inferred_relationships():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE categories (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      category_id INTEGER,
      FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """

    result = parse_sql_schema(sql, SqlDialect.POSTGRES)

    sources = {(r.from_column, r.source) for r in result.relationships}
    assert ("user_id", RelationshipSource.EXPLICIT) in sources
    assert ("category_id", RelationshipSource.INFERRED) in sources
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/schema_design/test_parse_sql_schema.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `apps/api/src/schema_design/application/parse_sql_schema.py`**

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/schema_design/test_parse_sql_schema.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full schema_design test suite to confirm no regressions**

Run: `pytest tests/schema_design/ -v`
Expected: all tests across every task in this plan PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/schema_design/application/parse_sql_schema.py apps/api/tests/schema_design/test_parse_sql_schema.py
git commit -m "feat(api): add ParseSqlSchema use case orchestrating parsing, relationships, and warnings"
```

---

### Task 10: Interfaces — `POST /api/schema/parse` endpoint

**Files:**
- Create: `apps/api/src/schema_design/interfaces/schemas.py`
- Create: `apps/api/src/schema_design/interfaces/router.py`
- Modify: `apps/api/src/main.py` (register the new router)
- Test: `apps/api/tests/schema_design/test_parse_endpoint.py`

**Interfaces:**
- Consumes: `parse_sql_schema` (Task 9), `SqlDialect`/`InvalidDialectError` (Phase 1), `error_body` (Phase 1, `apps/api/src/shared_kernel/errors.py`).
- Produces: the `POST /api/schema/parse` HTTP endpoint, matching the spec's API Contract section exactly.

- [ ] **Step 1: Write the failing tests — `apps/api/tests/schema_design/test_parse_endpoint.py`**

```python
def test_parse_endpoint_returns_tables_relationships_warnings(client):
    payload = {
        "sql": (
            "CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255) NOT NULL);"
            "CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL, "
            "FOREIGN KEY (user_id) REFERENCES users(id));"
        ),
        "dialect": "postgres",
    }

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 200
    body = response.json()
    table_names = {t["name"] for t in body["tables"]}
    assert table_names == {"users", "posts"}
    assert len(body["relationships"]) == 1
    assert body["relationships"][0]["source"] == "explicit"
    assert "warnings" in body


def test_parse_endpoint_returns_400_for_invalid_sql(client):
    payload = {"sql": "THIS IS NOT VALID SQL AT ALL (((", "dialect": "postgres"}

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"


def test_parse_endpoint_returns_400_for_invalid_dialect(client):
    payload = {"sql": "CREATE TABLE users (id INTEGER);", "dialect": "oracle"}

    response = client.post("/api/schema/parse", json=payload)

    assert response.status_code == 400
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/schema_design/test_parse_endpoint.py -v`
Expected: FAIL — 404 (no route registered yet). Note: this test uses the `client` fixture already defined in `apps/api/tests/conftest.py` (Phase 1) — no new fixture needed.

- [ ] **Step 3: Implement `apps/api/src/schema_design/interfaces/schemas.py`**

```python
from pydantic import BaseModel


class ParseSchemaRequest(BaseModel):
    sql: str
    dialect: str


class ColumnResponse(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class TableResponse(BaseModel):
    name: str
    columns: list[ColumnResponse]


class RelationshipResponse(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    type: str
    source: str


class WarningResponse(BaseModel):
    code: str
    table: str
    message: str


class ParseSchemaResponse(BaseModel):
    tables: list[TableResponse]
    relationships: list[RelationshipResponse]
    warnings: list[WarningResponse]
```

- [ ] **Step 4: Implement `apps/api/src/schema_design/interfaces/router.py`**

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlglot.errors import ParseError

from src.schema_design.application.parse_sql_schema import parse_sql_schema
from src.schema_design.domain.dialect import InvalidDialectError, SqlDialect
from src.schema_design.interfaces.schemas import (
    ColumnResponse,
    ParseSchemaRequest,
    ParseSchemaResponse,
    RelationshipResponse,
    TableResponse,
    WarningResponse,
)
from src.shared_kernel.errors import error_body

router = APIRouter(prefix="/api/schema", tags=["schema_design"])


@router.post("/parse")
def parse_schema(request: ParseSchemaRequest):
    try:
        dialect = SqlDialect.from_string(request.dialect)
    except InvalidDialectError as exc:
        return JSONResponse(status_code=400, content=error_body("invalid_dialect", str(exc)))

    try:
        result = parse_sql_schema(request.sql, dialect)
    except ParseError as exc:
        return JSONResponse(status_code=400, content=error_body("invalid_sql", str(exc)))

    response = ParseSchemaResponse(
        tables=[
            TableResponse(
                name=table.name,
                columns=[
                    ColumnResponse(
                        name=c.name, type=c.type, nullable=c.nullable, primary_key=c.primary_key
                    )
                    for c in table.columns
                ],
            )
            for table in result.tables
        ],
        relationships=[
            RelationshipResponse(
                from_table=r.from_table,
                from_column=r.from_column,
                to_table=r.to_table,
                to_column=r.to_column,
                type=r.type.value,
                source=r.source.value,
            )
            for r in result.relationships
        ],
        warnings=[
            WarningResponse(code=w.code.value, table=w.table, message=w.message) for w in result.warnings
        ],
    )
    return response
```

- [ ] **Step 5: Register the router in `apps/api/src/main.py`**

```python
from src.schema_design.interfaces.router import router as schema_design_router

def create_app() -> FastAPI:
    # ... existing settings/middleware/health-router setup ...
    app.include_router(schema_design_router)
    return app
```

Add the import alongside the existing `health_router` import, and add `app.include_router(schema_design_router)` right after the existing `app.include_router(health_router)` line, before `return app`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `pytest tests/schema_design/test_parse_endpoint.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Run the full `apps/api` test suite**

Run: `pytest -v` (from `apps/api`)
Expected: every test in the project passes, including Phase 1's health/dialect/settings tests and this plan's schema_design tests.

- [ ] **Step 8: Run Ruff**

Run: `ruff check .` and `ruff format --check .` (from `apps/api`)
Expected: 0 errors. Fix any findings before committing.

- [ ] **Step 9: Manual spot-check via Swagger**

Run: `uvicorn src.main:app --reload` (from `apps/api`), open `http://127.0.0.1:8000/docs`, find `POST /api/schema/parse`, try it with a real multi-table SQL script, confirm the response shape matches the spec's example. Stop the server after confirming.

- [ ] **Step 10: Commit**

```bash
git add apps/api/src/schema_design/interfaces apps/api/src/main.py apps/api/tests/schema_design/test_parse_endpoint.py
git commit -m "feat(api): add POST /api/schema/parse endpoint"
```

---

### Task 11: Regenerate `packages/api-client` and update CI's drift check

**Files:**
- Modify: `packages/api-client/openapi.json` (regenerated, gitignored — not committed)
- Modify: `packages/api-client/src/schema.ts` (regenerated, committed)

**Interfaces:**
- Consumes: the live OpenAPI schema now including `/api/schema/parse` (Task 10).
- Produces: updated generated types available to `apps/web` in a future phase (Phase 4) — this task just keeps the Phase 1-built generation pipeline in sync; it doesn't wire any new frontend code (out of scope per this phase's spec).

- [ ] **Step 1: Regenerate the OpenAPI schema**

Run (from `apps/api`): `python scripts/export_openapi.py`
Expected: overwrites `packages/api-client/openapi.json` with a schema that now includes the `/api/schema/parse` path.

- [ ] **Step 2: Regenerate the TS types**

Run (from `packages/api-client`): `pnpm generate`
Expected: `src/schema.ts` is regenerated and now includes types for the new endpoint's request/response shapes.

- [ ] **Step 3: Verify the CI drift check would pass**

Run (from the repo root): `git diff --exit-code packages/api-client/src/schema.ts`
Expected: exits 0 only if you already staged/committed the regenerated file in this same step — first run `git add packages/api-client/src/schema.ts`, THEN run the diff check, which should show no further diff since the working tree now matches the index. (This is the same check Phase 1's `api-client-schema` CI job runs — you're verifying locally that CI will pass, not bypassing it.)

- [ ] **Step 4: Typecheck `apps/web` still passes with the updated generated types**

Run (from `apps/web`): `tsc --noEmit`
Expected: PASS — no code in `apps/web` references the new types yet (Phase 4's job), so this just confirms the regenerated file itself is syntactically valid TS that doesn't break the existing build.

- [ ] **Step 5: Commit**

```bash
git add packages/api-client/src/schema.ts
git commit -m "chore: regenerate api-client schema for POST /api/schema/parse"
```

---

## Self-Review Notes

- **Spec coverage:** dialect coverage (Task 5), explicit relationships + cardinality (Task 6), junction/many-to-many (Task 6), naming-convention inference tagged `"inferred"` (Task 7), all four structural warning codes (Task 8), API contract shape incl. 400 error paths (Task 10), api-client regeneration (Task 11). The spec's "Testing" section's Given/When/Then framing is realized as the specific test functions in each task rather than a separate document — every test function name states the behavior under test.
- **Placeholder scan:** the sqlglot-attribute-chain guidance in Tasks 3-5 is not a placeholder — it gives concrete test inputs/outputs and an exact exploration command, with a fallback instruction (re-run exploration, don't guess) for the one genuinely external unknown (sqlglot's exact AST shape for the installed version). Every other step has literal code.
- **Type consistency:** `RelationshipSource`/`RelationshipType`/`WarningCode` enum values defined in Task 2 are referenced identically (`.value` in Task 10's response serialization) everywhere downstream. `Table.find_column` (Task 1) is used by Task 6, 7, and 8 with the same signature. `extract_tables`/`extract_foreign_keys` (Tasks 3-4) return types match exactly what Task 9's use case destructures.
