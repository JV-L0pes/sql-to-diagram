# Review Findings Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every finding from the 2026-09-22 whole-repo review that is prudent to fix now, leaving production deployable, the SQL parser correct on real-world DDL, auth hardened, and CI guarding the failure modes that caused the outage.

**Architecture:** Keep the existing DDD layering (domain/application/infrastructure/interfaces per bounded context). Contract changes are allowed and must regenerate `packages/api-client`. No new runtime dependencies except `email-validator` (for Pydantic `EmailStr`).

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2 + SQLite (tests) / Postgres (prod) + Alembic + sqlglot 30.x; pnpm + Vite + React 19 + Vitest + Biome + ESLint; CI GitHub Actions; deploy Vercel (Python function in `api/`).

**Spec:** This plan implements the findings from the session review of `origin/main` (commit `64d3d08`) plus the phase specs in `docs/superpowers/specs/` (2026-09-16, 2026-09-17, 2026-09-18). Where the review and the phase specs disagree (e.g. empty SQL must be 400, not 200), the phase specs win.

## Global Constraints

- Python: `requires-python >= 3.12`; ruff `line-length = 100`, `target-version = "py312"`, lint `select = ["E","F","I","UP","B"]`; `ruff format` enforced in CI.
- Current sqlglot stable is **30.19.0**; set floor `sqlglot>=30.19.0` and keep the `Alter`/`AlterTable` compatibility tuple anyway.
- Deploy manifest is `api/requirements.txt` (what Vercel installs). `apps/api/pyproject.toml` is the dev/test manifest. They must contain the same runtime dependency names; a test enforces it.
- Error envelope for ALL API errors: `{"error": {"code": str, "message": str, "details"?: object}}` via `src.shared_kernel.errors.error_body`.
- `JWT_SECRET` must be at least 32 characters (Settings validation).
- Test env for all pytest runs (matches CI):
  `DATABASE_URL="postgresql+psycopg://ci:ci@localhost/ci_placeholder"`, `JWT_SECRET="ci_placeholder_jwt_secret_at_least_32_chars"`.
- Local venv used by this session: `%TEMP%\opencode\schemio-venv\Scripts\python.exe` (packages installed editable from `apps/api`). Run pytest with `workdir=apps/api`.
- Commits use the repo's existing Conventional Commit style (`fix(...)`, `feat(...)`, `chore(...)`, `docs(...)`).
- Do NOT push or open the PR until Task 9.

## Review Focus

Inputs/conditions the phase specs imply but current tests do not exercise, most likely to bite real users first:

1. **Real dump scripts** (pg_dump / migrations): `ALTER TABLE ... ADD COLUMN/PRIMARY KEY/UNIQUE`, bare `REFERENCES table`, statements other than `CREATE` — must parse or 400, never 500.
2. **Malformed/hostile SQL** (unterminated string, empty input, huge payload, `RECURSION` depth) — must be 400 or bounded, never 500/DoS.
3. **Token lifecycle edges**: replayed revoked refresh token, concurrent rotation, expiry boundary — must invalidate, never mint two sessions.
4. **Timestamps**: SQLite tests read naive, Postgres prod stores `timestamptz`; comparisons must not raise `TypeError` and round-trip consistently.
5. **Deploy manifest drift**: missing dependency in `api/requirements.txt` must fail CI, not production cold start.

---

### Task 1: Deploy manifest sync + CI guard

**Files:**
- Modify: `api/requirements.txt`
- Modify: `apps/api/pyproject.toml` (add `email-validator`, bump `sqlglot` floor)
- Create: `apps/api/tests/test_deployment_manifest.py`
- Modify: `.github/workflows/ci.yml` (add `deploy-manifest` job; update `JWT_SECRET` values)

**Interfaces:**
- Consumes: nothing.
- Produces: identical runtime dependency names across `apps/api/pyproject.toml` and `api/requirements.txt`; CI job `deploy-manifest` that pip-installs `api/requirements.txt` and imports `src.main`.

- [ ] **Step 1: Write the failing manifest-sync test**

Create `apps/api/tests/test_deployment_manifest.py`:

```python
import re
from pathlib import Path

API_PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
REQUIREMENTS = Path(__file__).resolve().parents[3] / "api" / "requirements.txt"

_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")


def _dependency_names(lines: list[str]) -> set[str]:
    names = set()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _NAME_RE.match(stripped)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def _pyproject_runtime_dependencies() -> set[str]:
    content = API_PYPROJECT.read_text(encoding="utf-8")
    block_match = re.search(r"^dependencies\s*=\s*\[(.*?)\]", content, re.M | re.S)
    assert block_match is not None, "could not find [project].dependencies in pyproject.toml"
    entries = re.findall(r'"([^"]+)"', block_match.group(1))
    return _dependency_names(entries)


def _requirements_dependencies() -> set[str]:
    return _dependency_names(REQUIREMENTS.read_text(encoding="utf-8").splitlines())


def test_deploy_manifest_lists_every_runtime_dependency() -> None:
    """Vercel installs api/requirements.txt only; it must not miss a runtime dep."""
    missing = _pyproject_runtime_dependencies() - _requirements_dependencies()
    assert missing == set(), (
        f"api/requirements.txt is missing runtime dependencies: {sorted(missing)}"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `%TEMP%\opencode\schemio-venv\Scripts\python.exe -m pytest tests/test_deployment_manifest.py -v` (workdir `apps/api`, env vars set)
Expected: FAIL listing missing `argon2-cffi`, `pyjwt`, `sqlglot` (and `email-validator` once step 3 adds it).

- [ ] **Step 3: Sync the manifests**

Replace `api/requirements.txt` with:

```
alembic>=1.14.0
argon2-cffi>=23.1.0
email-validator>=2.2.0
fastapi>=0.115.0
psycopg[binary]>=3.2.0
pydantic-settings>=2.6.0
PyJWT>=2.9.0
sqlalchemy>=2.0.35
sqlglot>=30.19.0
uvicorn[standard]>=0.32.0
```

In `apps/api/pyproject.toml` dependencies: add `"email-validator>=2.2.0"` and change `"sqlglot>=25.0.0"` to `"sqlglot>=30.19.0"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `%TEMP%\opencode\schemio-venv\Scripts\python.exe -m pip install --quiet -e ".[dev]"` then `pytest tests/test_deployment_manifest.py -v`
Expected: PASS.

- [ ] **Step 5: Add the CI deploy-manifest job**

In `.github/workflows/ci.yml`, update both existing `JWT_SECRET` env values to `ci_placeholder_jwt_secret_at_least_32_chars` (Settings will require >= 32 chars after Task 5). Append:

```yaml
  deploy-manifest:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: apps/api
    env:
      DATABASE_URL: postgresql+psycopg://ci:ci@localhost/ci_placeholder
      JWT_SECRET: ci_placeholder_jwt_secret_at_least_32_chars
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r ../../api/requirements.txt
      - run: python -c "from src.main import app; print(app.title)"
```

- [ ] **Step 6: Verify full suite still green**

Run: `pytest -q` (workdir `apps/api`)
Expected: 100 passed.

- [ ] **Step 7: Commit**

```bash
git add api/requirements.txt apps/api/pyproject.toml apps/api/tests/test_deployment_manifest.py .github/workflows/ci.yml
git commit -m "fix(deploy): sync api/requirements.txt with pyproject and guard it in CI"
```

---

### Task 2: sqlglot parser hardening

**Files:**
- Rewrite: `apps/api/src/schema_design/infrastructure/sqlglot_parser.py`
- Modify: `apps/api/src/schema_design/domain/dialect.py` (aliases)
- Modify: `apps/api/src/schema_design/application/parse_sql_schema.py` (single parse)
- Modify: `apps/api/src/schema_design/interfaces/router.py` (empty SQL, `SqlglotError`)
- Modify: `apps/api/tests/schema_design/test_sqlglot_parser.py`, `test_dialect.py`, `test_parse_endpoint.py`

**Interfaces:**
- Consumes: Task 1's sqlglot 30.19 floor.
- Produces:
  - `sqlglot_parser.ParsedSql(tables: list[Table], foreign_keys: list[tuple[str, str, str, str]])`
  - `sqlglot_parser.parse_sql(sql: str, dialect: SqlDialect) -> ParsedSql` (single `sqlglot.parse` call)
  - `extract_tables(sql, dialect) -> list[Table]` and `extract_foreign_keys(sql, dialect) -> list[tuple[...]]` keep working as thin wrappers.
  - `SqlDialect.from_string` accepts aliases `postgresql`, `pg`, `mariadb`, `sqlserver`, `sql_server`, `tsql`, `sqlite3`.
  - Router returns 400 `invalid_sql` for empty/whitespace SQL and any `sqlglot.errors.SqlglotError` (incl. `TokenError`).

- [ ] **Step 1: Write failing parser tests**

Add to `apps/api/tests/schema_design/test_sqlglot_parser.py` (keep existing tests; they must keep passing):

```python
def test_extract_foreign_keys_resolves_bare_reference_to_target_primary_key():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users);
    """
    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == [("posts", "user_id", "users", "id")]


def test_extract_foreign_keys_resolves_table_level_reference_without_column_list():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (
      id SERIAL PRIMARY KEY,
      user_id INTEGER NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users
    );
    """
    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == [("posts", "user_id", "users", "id")]


def test_extract_foreign_keys_raises_value_error_for_bare_reference_to_composite_pk():
    sql = """
    CREATE TABLE orders (a INTEGER, b INTEGER, PRIMARY KEY (a, b));
    CREATE TABLE items (id SERIAL PRIMARY KEY, order_id INTEGER REFERENCES orders);
    """
    with pytest.raises(ValueError):
        extract_foreign_keys(sql, SqlDialect.POSTGRES)


def test_extract_foreign_keys_skips_bare_reference_to_unknown_table():
    sql = "CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES missing_table);"
    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == []


def test_alter_table_add_column_is_merged_into_the_table():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL;
    """
    tables = extract_tables(sql, SqlDialect.POSTGRES)
    assert tables[0].find_column("email") is not None


def test_alter_table_add_primary_key_marks_column():
    sql = """
    CREATE TABLE users (id SERIAL);
    ALTER TABLE users ADD PRIMARY KEY (id);
    """
    tables = extract_tables(sql, SqlDialect.POSTGRES)
    assert tables[0].find_column("id").primary_key is True


def test_alter_table_add_unique_marks_column():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY, email VARCHAR(255));
    ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
    """
    tables = extract_tables(sql, SqlDialect.POSTGRES)
    assert tables[0].find_column("email").unique is True


def test_alter_table_add_column_with_inline_reference_is_extracted():
    sql = """
    CREATE TABLE users (id SERIAL PRIMARY KEY);
    CREATE TABLE posts (id SERIAL PRIMARY KEY);
    ALTER TABLE posts ADD COLUMN user_id INTEGER REFERENCES users;
    """
    assert extract_foreign_keys(sql, SqlDialect.POSTGRES) == [("posts", "user_id", "users", "id")]
```

Add to `apps/api/tests/schema_design/test_dialect.py`:

```python
def test_from_string_accepts_common_aliases():
    assert SqlDialect.from_string("PostgreSQL") is SqlDialect.POSTGRES
    assert SqlDialect.from_string("postgres") is SqlDialect.POSTGRES
    assert SqlDialect.from_string("mariadb") is SqlDialect.MYSQL
    assert SqlDialect.from_string("SQLServer") is SqlDialect.MSSQL
    assert SqlDialect.from_string("sqlite3") is SqlDialect.SQLITE
```

Add to `apps/api/tests/schema_design/test_parse_endpoint.py`:

```python
import pytest


@pytest.mark.parametrize("sql", ["", "   \n  "])
def test_parse_endpoint_returns_400_for_empty_sql(client, sql):
    response = client.post("/api/schema/parse", json={"sql": sql, "dialect": "postgres"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"


def test_parse_endpoint_returns_400_for_tokenizer_error(client):
    payload = {"sql": "CREATE TABLE t (name TEXT 'unterminated", "dialect": "postgres"}
    response = client.post("/api/schema/parse", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_sql"


def test_parse_endpoint_handles_bare_references_without_500(client):
    payload = {
        "sql": (
            "CREATE TABLE users (id SERIAL PRIMARY KEY);"
            "CREATE TABLE posts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users);"
        ),
        "dialect": "postgres",
    }
    response = client.post("/api/schema/parse", json=payload)
    assert response.status_code == 200
    assert response.json()["relationships"][0]["to_column"] == "id"
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `pytest tests/schema_design -q` (workdir `apps/api`)
Expected: FAILs: `IndexError` for bare REFERENCES, `AttributeError`-free 500 for empty SQL? (empty actually returns 200 currently), aliases `InvalidDialectError`, `Column` has no `unique` (that arrives in Task 3 — for now `test_alter_table_add_unique_marks_column` fails with `TypeError`). **Task 3 owns the `unique` field**; if executing strictly task-by-task, skip that one test here and add it in Task 3. All other new tests must fail now.

- [ ] **Step 3: Rewrite the parser**

Rewrite `apps/api/src/schema_design/infrastructure/sqlglot_parser.py`:

```python
from dataclasses import dataclass, replace

import sqlglot
from sqlglot import exp

from src.schema_design.domain.dialect import SqlDialect
from src.schema_design.domain.table import Column, Table

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


def parse_sql(sql: str, dialect: SqlDialect) -> ParsedSql:
    """Parse SQL text once and extract tables plus deduplicated foreign keys."""
    statements = sqlglot.parse(sql, read=_sqlglot_dialect(dialect))
    tables = _extract_tables(statements, dialect)
    _apply_alter_statements(statements, tables, dialect)
    foreign_keys = _extract_foreign_keys(statements, tables)
    return ParsedSql(tables=tables, foreign_keys=foreign_keys)


def extract_tables(sql: str, dialect: SqlDialect) -> list[Table]:
    return parse_sql(sql, dialect).tables


def extract_foreign_keys(sql: str, dialect: SqlDialect) -> list[ForeignKeyTuple]:
    return parse_sql(sql, dialect).foreign_keys


def _extract_tables(statements: list[exp.Expr | None], dialect: SqlDialect) -> list[Table]:
    tables: list[Table] = []
    for statement in statements:
        if isinstance(statement, exp.Create) and statement.args.get("kind") == "TABLE":
            tables.append(_extract_table(statement, dialect))
    return tables


def _extract_table(create_stmt: exp.Create, dialect: SqlDialect) -> Table:
    schema_expr = create_stmt.this
    table_name = schema_expr.this.name

    column_defs = [item for item in schema_expr.expressions if isinstance(item, exp.ColumnDef)]
    primary_key_columns = _collect_primary_key_columns(schema_expr.expressions)
    single_unique, composite_unique = _collect_unique_constraints(schema_expr.expressions)

    columns = [
        _extract_column(column_def, dialect, primary_key_columns, single_unique)
        for column_def in column_defs
    ]
    return Table(name=table_name, columns=columns, unique_constraints=composite_unique)


def _collect_primary_key_columns(expressions: list[exp.Expr]) -> set[str]:
    names: set[str] = set()
    for item in expressions:
        if isinstance(item, exp.PrimaryKey):
            names.update(column.name for column in item.expressions)
    return names


def _collect_unique_constraints(
    expressions: list[exp.Expr],
) -> tuple[set[str], list[tuple[str, ...]]]:
    single: set[str] = set()
    composite: list[tuple[str, ...]] = []
    for item in expressions:
        if isinstance(item, exp.UniqueColumnConstraint) and isinstance(item.this, exp.Schema):
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

    nullable = not (is_not_null or is_primary_key)
    return Column(
        name=name, type=type_str, nullable=nullable, primary_key=is_primary_key, unique=is_unique
    )


def _apply_alter_statements(
    statements: list[exp.Expr | None], tables: list[Table], dialect: SqlDialect
) -> None:
    tables_by_name = {table.name: table for table in tables}
    for statement in statements:
        if not isinstance(statement, _ALTER_NODE_TYPES):
            continue
        table = tables_by_name.get(statement.this.this.name)
        if table is None:
            continue
        for action in statement.args.get("actions") or []:
            for column_def in action.find_all(exp.ColumnDef):
                if table.find_column(column_def.this.name) is None:
                    table.columns.append(
                        _extract_column(column_def, dialect, set(), set())
                    )
            for primary_key in action.find_all(exp.PrimaryKey):
                for column in primary_key.expressions:
                    _replace_column(
                        table, column.name, primary_key=True, nullable=False
                    )
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


def _extract_foreign_keys(statements: list[exp.Expr | None], tables: list[Table]) -> list[ForeignKeyTuple]:
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
    from_table = create_stmt.this.this.name

    for item in create_stmt.this.expressions:
        if isinstance(item, exp.ForeignKey):
            results.extend(
                _resolve_foreign_key(
                    from_table,
                    [column.name for column in item.expressions],
                    item.args["reference"],
                    tables_by_name,
                )
            )
        elif isinstance(item, exp.ColumnDef):
            for constraint in item.constraints:
                if isinstance(constraint.kind, exp.Reference):
                    results.extend(
                        _resolve_foreign_key(
                            from_table,
                            [item.this.name],
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
    from_table = alter_stmt.this.this.name

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
        to_table = target.this.name
        to_columns = [column.name for column in target.expressions]
    else:
        to_table = target.name
        to_columns = []

    if not to_columns:
        to_columns = _single_primary_key_columns(tables_by_name.get(to_table))
        if not to_columns:
            return []

    if len(from_columns) != len(to_columns):
        raise ValueError(
            f"FOREIGN KEY ({', '.join(from_columns)}) on table '{from_table}' references "
            f"{len(to_columns)} column(s) on '{to_table}' but provides {len(from_columns)}"
        )

    return [
        (from_table, from_column, to_table, to_column)
        for from_column, to_column in zip(from_columns, to_columns)
    ]


def _single_primary_key_columns(table: Table | None) -> list[str]:
    if table is None:
        return []
    return [column.name for column in table.columns if column.primary_key]
```

Note: this step references `Column.unique` and `Table.unique_constraints` which arrive in Task 3. If executing strictly task-by-task, add those two domain changes now (they are one-line additions; Task 3's tests build on them). **Recommended: pull Task 3 Step 3's domain change forward into this step** so the tree is green at the Task 2 commit.

- [ ] **Step 4: Update the use case to parse once**

`apps/api/src/schema_design/application/parse_sql_schema.py` becomes:

```python
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
```

- [ ] **Step 5: Add dialect aliases**

In `apps/api/src/schema_design/domain/dialect.py`, replace the whole file body with (note `_ALIASES` is defined **after** the class — Python resolves it at call time):

```python
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
```

- [ ] **Step 6: Harden the router**

In `apps/api/src/schema_design/interfaces/router.py`:
- Replace `from sqlglot.errors import ParseError` with `from sqlglot.errors import SqlglotError`.
- Add `import re` and at module level:

```python
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _invalid_sql(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_body("invalid_sql", _ANSI_ESCAPE_RE.sub("", message)),
    )
```

- At the top of `parse_schema`, before dialect parsing:

```python
    if not request.sql.strip():
        return _invalid_sql("SQL input is empty.")
```

- Change the parse catch to:

```python
    try:
        result = parse_sql_schema(request.sql, dialect)
    except (SqlglotError, ValueError) as exc:
        return _invalid_sql(str(exc))
```

- [ ] **Step 7: Run the schema_design suite**

Run: `pytest tests/schema_design -q` (workdir `apps/api`)
Expected: all pass (the `unique` tests pass thanks to the pulled-forward domain change).

- [ ] **Step 8: Run the full suite + ruff**

Run: `pytest -q; ruff check .; ruff format --check .` (workdir `apps/api`)
Expected: ~107 passed, no lint/format issues (`ruff format` may need to be run to fix formatting).

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/schema_design apps/api/tests/schema_design
git commit -m "fix(schema-design): parse once, resolve bare REFERENCES, handle ALTER DDL and TokenError"
```

---

### Task 3: UNIQUE in the domain, relationship detection fixes, typed response contract

**Files:**
- Modify: `apps/api/src/schema_design/domain/table.py` (`Column.unique`, `Table.unique_constraints`)
- Modify: `apps/api/src/schema_design/domain/relationship.py` (`Relationship.via_table`)
- Modify: `apps/api/src/schema_design/infrastructure/relationship_detector.py`
- Modify: `apps/api/src/schema_design/interfaces/schemas.py` + `router.py` (typed enums, `unique`, `via_table`)
- Modify tests: `tests/schema_design/test_table.py`, `test_relationship.py`, `test_relationship_detector.py`
- Regenerate: `packages/api-client/src/schema.ts` (+ commit `packages/api-client/openapi.json`, still untracked until Task 7)

**Interfaces:**
- Consumes: Task 2's parser (which already reads UNIQUE constraints into `Table.unique_constraints` / `Column.unique`).
- Produces:
  - `Column(name, type, nullable, primary_key, unique: bool = False)`
  - `Table(name, columns, unique_constraints: list[tuple[str, ...]] = [])`
  - `Relationship(..., via_table: str | None = None)`
  - `ColumnResponse.unique: bool`, `RelationshipResponse.via_table: str | None`, `RelationshipResponse.type: RelationshipType`, `.source: RelationshipSource`, `WarningResponse.code: WarningCode` (enums serialized to their string values in both OpenAPI and JSON).

- [ ] **Step 1: Write failing domain/detector tests**

Add to `tests/schema_design/test_table.py`:

```python
def test_column_unique_defaults_to_false_and_table_starts_without_unique_constraints():
    table = Table(name="users", columns=[Column("id", "INTEGER", False, True)])
    assert table.columns[0].unique is False
    assert table.unique_constraints == []
```

Add to `tests/schema_design/test_relationship.py`:

```python
def test_relationship_via_table_defaults_to_none():
    rel = Relationship(
        "posts", "user_id", "users", "id", RelationshipType.MANY_TO_ONE,
        RelationshipSource.EXPLICIT,
    )
    assert rel.via_table is None
```

Add to `tests/schema_design/test_relationship_detector.py`:

```python
def test_composite_pk_member_is_not_treated_as_individually_unique():
    orders = _table("orders", [Column("id", "INTEGER", False, True)])
    tickets = _table(
        "tickets",
        [
            Column("order_id", "INTEGER", False, True),
            Column("seq", "INTEGER", False, True),
            Column("id", "INTEGER", False, False),
        ],
    )
    # order_id may be any of many tickets per order: must stay MANY_TO_ONE
    foreign_keys = [("tickets", "order_id", "orders", "id")]

    relationships = detect_explicit_relationships([orders, tickets], foreign_keys)

    assert relationships[0].type == RelationshipType.MANY_TO_ONE


def test_explicit_unique_flag_makes_relationship_one_to_one():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    profiles = _table(
        "profiles",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False, True),  # UNIQUE
        ],
    )
    foreign_keys = [("profiles", "user_id", "users", "id")]

    relationships = detect_explicit_relationships([users, profiles], foreign_keys)

    assert relationships[0].type == RelationshipType.ONE_TO_ONE


def test_two_fks_to_the_same_table_are_not_collapsed_into_many_to_many():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    friendships = _table(
        "friendships",
        [
            Column("user_a_id", "INTEGER", False, False),
            Column("user_b_id", "INTEGER", False, False),
        ],
    )
    foreign_keys = [
        ("friendships", "user_a_id", "users", "id"),
        ("friendships", "user_b_id", "users", "id"),
    ]

    relationships = detect_explicit_relationships([users, friendships], foreign_keys)

    assert all(r.type != RelationshipType.MANY_TO_MANY for r in relationships)
    assert len(relationships) == 2


def test_surrogate_pk_junction_with_composite_unique_collapses_to_many_to_many():
    students = _table("students", [Column("id", "INTEGER", False, True)])
    courses = _table("courses", [Column("id", "INTEGER", False, True)])
    enrollments = Table(
        name="enrollments",
        columns=[
            Column("id", "INTEGER", False, True),
            Column("student_id", "INTEGER", False, False),
            Column("course_id", "INTEGER", False, False),
        ],
        unique_constraints=[("student_id", "course_id")],
    )
    foreign_keys = [
        ("enrollments", "student_id", "students", "id"),
        ("enrollments", "course_id", "courses", "id"),
    ]

    relationships = detect_explicit_relationships([students, courses, enrollments], foreign_keys)

    many_to_many = [r for r in relationships if r.type == RelationshipType.MANY_TO_MANY]
    assert {(r.from_table, r.to_table) for r in many_to_many} == {
        ("students", "courses"),
        ("courses", "students"),
    }
    assert all(r.via_table == "enrollments" for r in many_to_many)


def test_infers_to_single_column_primary_key_not_named_id():
    parents = _table("parents", [Column("uuid", "TEXT", False, True)])
    children = _table(
        "children",
        [
            Column("id", "INTEGER", False, True),
            Column("parent_id", "TEXT", False, False),
        ],
    )

    relationships = detect_inferred_relationships([parents, children], [], [])

    assert len(relationships) == 1
    assert relationships[0].to_table == "parents"
    assert relationships[0].to_column == "uuid"


def test_does_not_infer_when_target_id_column_is_not_a_key():
    categories = _table("categories", [Column("id", "INTEGER", False, False)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("category_id", "INTEGER", False, False),
        ],
    )

    assert detect_inferred_relationships([categories, posts], [], []) == []


def test_does_not_infer_when_multiple_tables_match_the_prefix():
    users = _table("users", [Column("id", "INTEGER", False, True)])
    usera = _table("usera", [Column("id", "INTEGER", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INTEGER", False, True),
            Column("user_id", "INTEGER", False, False),
        ],
    )

    assert detect_inferred_relationships([users, usera, posts], [], []) == []


def test_infers_when_types_differ_only_by_unsigned_modifier():
    users = _table("users", [Column("id", "INT", False, True)])
    posts = _table(
        "posts",
        [
            Column("id", "INT", False, True),
            Column("user_id", "INT UNSIGNED", False, False),
        ],
    )

    relationships = detect_inferred_relationships([users, posts], [], [])

    assert len(relationships) == 1
```

Update the existing `test_collapses_junction_table_into_many_to_many` to also assert:

```python
    assert all(r.via_table == "enrollments" for r in many_to_many)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/schema_design/test_relationship_detector.py tests/schema_design/test_table.py -q` (workdir `apps/api`)
Expected: FAIL — `unique`/`via_table` missing or detection assertions failing (composite-PK test currently yields `ONE_TO_ONE`).

- [ ] **Step 3: Update the domain model**

`apps/api/src/schema_design/domain/table.py`:

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    nullable: bool
    primary_key: bool
    unique: bool = False


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    unique_constraints: list[tuple[str, ...]] = field(default_factory=list)

    def find_column(self, name: str) -> Column | None:
        for column in self.columns:
            if column.name == name:
                return column
        return None
```

`apps/api/src/schema_design/domain/relationship.py`: add `via_table: str | None = None` as the last field of `Relationship`.

- [ ] **Step 4: Fix the detector**

In `apps/api/src/schema_design/infrastructure/relationship_detector.py`:

Replace `_identify_junction_tables` with:

```python
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
```

In the M2M emission block of `detect_explicit_relationships`, set `via_table=junction_name` on both `Relationship(...)` calls.

Replace `_is_column_unique` with:

```python
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
```

Replace the target-resolution part of `detect_inferred_relationships`:

```python
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
```

Replace `_are_types_compatible` and `_find_matching_table` with:

```python
_INTEGER_TYPE_NAMES = {
    "int", "integer", "bigint", "smallint", "serial", "bigserial", "tinyint", "mediumint",
}
_STRING_TYPE_NAMES = {"varchar", "char", "character", "text", "string", "nvarchar", "nchar", "clob"}
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

    matches = [name for name in table_names if name != exclude and name.lower() in candidates]
    # Ambiguous matches (>1) are skipped rather than guessed.
    if len(matches) != 1:
        return None
    return matches[0]
```

- [ ] **Step 5: Update the response contract**

`apps/api/src/schema_design/interfaces/schemas.py`:

```python
from pydantic import BaseModel, Field

from src.schema_design.domain.relationship import RelationshipSource, RelationshipType
from src.schema_design.domain.warning import WarningCode


class ParseSchemaRequest(BaseModel):
    sql: str = Field(max_length=500_000)
    dialect: str


class ColumnResponse(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool
    unique: bool


class TableResponse(BaseModel):
    name: str
    columns: list[ColumnResponse]


class RelationshipResponse(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    type: RelationshipType
    source: RelationshipSource
    via_table: str | None


class WarningResponse(BaseModel):
    code: WarningCode
    table: str
    message: str


class ParseSchemaResponse(BaseModel):
    tables: list[TableResponse]
    relationships: list[RelationshipResponse]
    warnings: list[WarningResponse]
```

In `router.py`, pass the new fields: `unique=c.unique` in `ColumnResponse(...)` and `via_table=r.via_table` in `RelationshipResponse(...)`. The `warnings=[WarningResponse(code=w.code, ...)]` line keeps working because `WarningCode` is a `StrEnum`.

- [ ] **Step 6: Run the schema_design suite**

Run: `pytest tests/schema_design -q` (workdir `apps/api`)
Expected: all pass.

- [ ] **Step 7: Regenerate the API client**

Run (with env vars set):

```powershell
cd apps/api; python scripts/export_openapi.py; cd ..\..\packages\api-client; pnpm generate
```

Expected: `packages/api-client/src/schema.ts` now contains `unique`, `via_table`, and enum unions; no other unexpected diff.

- [ ] **Step 8: Full suite + lint + format, then commit**

Run: `pytest -q; ruff check .; ruff format --check .` (workdir `apps/api`)
Expected: clean.

```bash
git add apps/api/src apps/api/tests apps/api/alembic packages/api-client/src/schema.ts packages/api-client/openapi.json
git commit -m "feat(schema-design): parse UNIQUE constraints, fix cardinality and junction detection"
```

---

### Task 4: Identity auth hardening

**Files:**
- Modify: `apps/api/src/identity/infrastructure/password_hasher.py`
- Modify: `apps/api/src/identity/application/authenticate_user.py`, `register_user.py`, `refresh_access_token.py`, `logout.py`
- Modify: `apps/api/src/identity/infrastructure/refresh_token_repository.py`, `user_repository.py`
- Modify: `apps/api/src/identity/domain/errors.py`
- Modify: `apps/api/src/identity/interfaces/schemas.py`
- Modify: `apps/api/src/identity/interfaces/auth_router.py` (only if needed for new outcome handling — the use case raises, so no change expected)
- Modify: `apps/api/src/shared_kernel/settings.py` (JWT secret min length)
- Modify tests: `tests/identity/test_password_hasher.py`, `test_authenticate_user.py`, `test_register_user.py`, `test_refresh_and_logout.py`, `test_refresh_token_repository.py`, `test_auth_endpoints.py`, `tests/shared_kernel/test_settings.py`

**Interfaces:**
- Consumes: Task 1's CI secret value (>= 32 chars).
- Produces:
  - `PasswordHasher.verify` returns `False` for corrupt/unsupported hashes (no exception).
  - `RefreshTokenRepository.rotate(old_token_hash: str, new_id: str, new_token_hash: str, new_expires_at: datetime) -> tuple[RotationOutcome, str | None]` with `RotationOutcome = StrEnum("ROTATED","INVALID","REUSED")`; on `REUSED` it revokes every active token of that user in the same transaction.
  - `RefreshTokenRepository.revoke_all_for_user(user_id: str) -> None`
  - `RegisterUser.execute` normalizes email (`strip().lower()`) and maps duplicate-insert `IntegrityError` to `EmailAlreadyRegisteredError`.
  - `AuthenticateUser.execute` also normalizes email and performs a dummy verify for unknown emails.
  - `RegisterRequest.email: EmailStr`, `LoginRequest.email: EmailStr`, `password` max length 128; `ProjectCreateRequest`/`UpdateRequest` names `min_length=1`.

- [ ] **Step 1: Write failing tests**

Add to `tests/identity/test_password_hasher.py`:

```python
def test_verify_returns_false_for_a_corrupt_hash_instead_of_raising():
    hasher = PasswordHasher()
    assert hasher.verify("not-an-argon2-hash", "anything") is False
```

Add to `tests/identity/test_authenticate_user.py`:

```python
def test_unknown_email_still_performs_a_dummy_password_verification():
    session = _make_session()
    _register(session)
    hasher = PasswordHasher()
    calls: list[str] = []
    original_verify = hasher.verify

    def recording_verify(password_hash: str, password: str) -> bool:
        calls.append(password_hash)
        return original_verify(password_hash, password)

    hasher.verify = recording_verify  # type: ignore[method-assign]
    use_case = AuthenticateUser(
        UserRepository(session), hasher, JwtService(secret="test-secret"),
        RefreshTokenRepository(session),
    )

    with pytest.raises(InvalidCredentialsError):
        use_case.execute("missing@example.com", "anything")

    assert len(calls) == 1  # constant-time: a verify runs even without a user


def test_email_is_normalized_before_lookup():
    session = _make_session()
    _register(session, email="a@example.com")
    use_case = _make_use_case(session)

    tokens = use_case.execute("  A@Example.COM ", "correct horse battery staple")

    assert tokens.access_token
```

Add to `tests/identity/test_register_user.py`:

```python
from sqlalchemy.exc import IntegrityError  # noqa: F401  (used by the fake below)


class _AlwaysMissUserRepository:
    """Simulates losing the check-then-create race: get_by_email misses, insert collides."""

    def __init__(self, real_repository):
        self._real = real_repository

    def get_by_email(self, email):
        return None

    def create(self, **kwargs):
        return self._real.create(**kwargs)


def test_maps_integrity_error_race_to_email_already_registered():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    real = UserRepository(session)
    use_case = RegisterUser(real, PasswordHasher())
    use_case.execute("a@example.com", "correct horse battery staple")

    racing = RegisterUser(_AlwaysMissUserRepository(real), PasswordHasher())
    with pytest.raises(EmailAlreadyRegisteredError):
        racing.execute("A@EXAMPLE.COM", "another password")


def test_email_is_normalized_on_register():
    use_case = _make_use_case()
    user = use_case.execute("  A@Example.COM ", "correct horse battery staple")
    assert user.email == "a@example.com"
```

Add to `tests/identity/test_refresh_and_logout.py`:

```python
def test_reusing_a_revoked_token_revokes_the_whole_token_family():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))
    first = _issue_raw_token(repo)
    other_session_token = _issue_raw_token(repo)
    rotated = use_case.execute(first).refresh_token

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(first)  # replay of the already-rotated token

    # every active token for that user was revoked as a precaution
    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(rotated)
    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(other_session_token)


def test_rotation_rejects_an_expired_token():
    import uuid
    from datetime import datetime, timedelta

    session = _make_session()
    repo = RefreshTokenRepository(session)
    raw = "expired-token"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    repo.create(
        id=str(uuid.uuid4()), user_id="u1", token_hash=token_hash,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(raw)
```

Add to `tests/shared_kernel/test_settings.py`:

```python
from pydantic import ValidationError


def test_settings_rejects_a_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET", "too-short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/identity tests/shared_kernel -q` (workdir `apps/api`)
Expected: FAIL on dummy-verify (no call recorded), normalization, corruption, short-secret, family revocation.

- [ ] **Step 3: Harden PasswordHasher**

`apps/api/src/identity/infrastructure/password_hasher.py`:

```python
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    def __init__(self):
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            # VerifyMismatchError subclasses VerificationError; InvalidHashError covers
            # corrupt/unsupported stored hashes. Never leak a 500 for bad stored data.
            return False
```

- [ ] **Step 4: Timing-safe login + email normalization**

`authenticate_user.py` changes:

```python
# Verified against for unknown emails so response time does not reveal whether
# the account exists. The password below is not a secret.
_DUMMY_HASH = PasswordHasher().hash("dummy-password-for-timing-equalization")


class AuthenticateUser:
    ...
    def execute(self, email: str, password: str) -> TokenPair:
        normalized_email = email.strip().lower()
        user = self._user_repository.get_by_email(normalized_email)
        if user is None:
            self._password_hasher.verify(_DUMMY_HASH, password)
            raise InvalidCredentialsError()
        if not self._password_hasher.verify(user.password_hash, password):
            raise InvalidCredentialsError()

        access_token = self._jwt_service.create_access_token(user.id)
        refresh_token = self._issue_refresh_token(user.id)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)
```

- [ ] **Step 5: Atomic rotation with reuse detection**

`refresh_token_repository.py`: add `from enum import StrEnum`, then:

```python
class RotationOutcome(StrEnum):
    ROTATED = "rotated"
    INVALID = "invalid"
    REUSED = "reused"


class RefreshTokenRepository:
    ...
    def rotate(
        self,
        old_token_hash: str,
        new_id: str,
        new_token_hash: str,
        new_expires_at: datetime,
    ) -> tuple[RotationOutcome, str | None]:
        """Atomically revoke the old token and issue a replacement.

        Returns (ROTATED, user_id) on success. A revoked token being presented again
        (REUSED) revokes every active token of that user in the same transaction
        (stolen-token defense). FOR UPDATE serializes concurrent rotations on Postgres;
        SQLite (tests) ignores it.
        """
        now = datetime.now(UTC)
        model = (
            self._session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.token_hash == old_token_hash)
            .with_for_update()
            .first()
        )
        if model is None or _as_utc(model.expires_at) <= now:
            return RotationOutcome.INVALID, None
        if model.revoked_at is not None:
            self._revoke_all_for_user_in_transaction(model.user_id, now)
            self._session.commit()
            return RotationOutcome.REUSED, None

        model.revoked_at = now
        self._session.add(
            RefreshTokenModel(
                id=new_id,
                user_id=model.user_id,
                token_hash=new_token_hash,
                expires_at=new_expires_at,
            )
        )
        self._session.commit()
        return RotationOutcome.ROTATED, model.user_id

    def revoke_all_for_user(self, user_id: str) -> None:
        self._revoke_all_for_user_in_transaction(user_id, datetime.now(UTC))
        self._session.commit()

    def _revoke_all_for_user_in_transaction(self, user_id: str, now: datetime) -> None:
        self._session.query(RefreshTokenModel).filter(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked_at.is_(None),
        ).update({"revoked_at": now})
```

Add module helper (also used by Task 6; keep it here for now):

```python
def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
```

`refresh_access_token.py` becomes:

```python
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from src.identity.application.authenticate_user import TokenPair
from src.identity.domain.errors import InvalidRefreshTokenError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.refresh_token_repository import (
    RefreshTokenRepository,
    RotationOutcome,
)


class RefreshAccessToken:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        jwt_service: JwtService,
        refresh_token_expiry_days: int = 30,
    ):
        self._refresh_token_repository = refresh_token_repository
        self._jwt_service = jwt_service
        self._refresh_token_expiry_days = refresh_token_expiry_days

    def execute(self, raw_refresh_token: str) -> TokenPair:
        old_token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        new_raw_token = secrets.token_urlsafe(32)
        new_token_hash = hashlib.sha256(new_raw_token.encode()).hexdigest()

        outcome, user_id = self._refresh_token_repository.rotate(
            old_token_hash=old_token_hash,
            new_id=str(uuid.uuid4()),
            new_token_hash=new_token_hash,
            new_expires_at=datetime.now(UTC) + timedelta(days=self._refresh_token_expiry_days),
        )
        if outcome is not RotationOutcome.ROTATED or user_id is None:
            raise InvalidRefreshTokenError()

        access_token = self._jwt_service.create_access_token(user_id)
        return TokenPair(access_token=access_token, refresh_token=new_raw_token)
```

- [ ] **Step 6: Registration race + normalization**

`register_user.py`:

```python
import uuid

from sqlalchemy.exc import IntegrityError

from src.identity.domain.errors import EmailAlreadyRegisteredError
from src.identity.domain.user import User
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.user_repository import UserRepository


class RegisterUser:
    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    def execute(self, email: str, password: str) -> User:
        normalized_email = email.strip().lower()
        if self._user_repository.get_by_email(normalized_email) is not None:
            raise EmailAlreadyRegisteredError(normalized_email)

        password_hash = self._password_hasher.hash(password)
        try:
            return self._user_repository.create(
                id=str(uuid.uuid4()), email=normalized_email, password_hash=password_hash
            )
        except IntegrityError as exc:
            # Lost the check-then-create race: the unique constraint is the source of truth.
            raise EmailAlreadyRegisteredError(normalized_email) from exc
```

`user_repository.create`: wrap the commit so the session is usable after a constraint failure:

```python
    def create(self, id: str, email: str, password_hash: str) -> User:
        model = UserModel(id=id, email=email, password_hash=password_hash)
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        self._session.refresh(model)
        return self._to_domain(model)
```

Add `from sqlalchemy.exc import IntegrityError` to that module.

`domain/errors.py`: make the message generic (no email echo):

```python
class EmailAlreadyRegisteredError(ValueError):
    def __init__(self, email: str):
        super().__init__("Email already registered")
```

(keep the parameter so call sites stay unchanged).

- [ ] **Step 7: Harden request schemas + settings**

`identity/interfaces/schemas.py`:
- `from pydantic import BaseModel, EmailStr, Field, field_validator`
- `RegisterRequest`: `email: EmailStr = Field(max_length=255)`, `password: str = Field(min_length=8, max_length=128)`
- `LoginRequest`: `email: EmailStr`, `password: str = Field(max_length=128)`
- Introduce a shared base to remove the duplicated dialect validator:

```python
class ProjectRequestBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sql: str
    dialect: str

    @field_validator("dialect")
    @classmethod
    def validate_dialect(cls, value: str) -> str:
        return SqlDialect.from_string(value).value


class ProjectCreateRequest(ProjectRequestBase):
    pass


class ProjectUpdateRequest(ProjectRequestBase):
    pass
```

`shared_kernel/settings.py`:

```python
from pydantic import Field, field_validator
...
    database_url: str
    jwt_secret: str = Field(min_length=32)
    cors_allow_origins: list[str] = ["http://localhost:5173"]
```

- [ ] **Step 8: Run tests**

Run: `pytest tests/identity tests/shared_kernel -q` (workdir `apps/api`)
Expected: all pass. Note: `test_auth_endpoints.test_login_rejects_wrong_password` uses password `"wrong"` (< 8 chars) — with `max_length=128` only (no login min), it still reaches the use case, so the test keeps passing. If `EmailStr` rejects any existing test email, fix the test data (all current emails are valid).

- [ ] **Step 9: Full suite + lint/format, then commit**

Run: `pytest -q; ruff check .; ruff format --check .` (workdir `apps/api`)

```bash
git add apps/api/src apps/api/tests
git commit -m "fix(identity): timing-safe login, atomic token rotation with reuse detection, email normalization"
```

---

### Task 5: Unified error envelope, health 503, projects pagination, settings cache, misc

**Files:**
- Modify: `apps/api/src/main.py` (validation + HTTP exception handlers)
- Modify: `apps/api/src/health/interfaces.py` (503 on DB failure)
- Modify: `apps/api/src/shared_kernel/settings.py` (`lru_cache`)
- Modify: `apps/api/src/shared_kernel/errors.py` (return type)
- Modify: `apps/api/src/identity/application/project_use_cases.py`, `infrastructure/project_repository.py`, `interfaces/projects_router.py` (pagination)
- Modify: `apps/api/alembic/env.py`, `apps/api/scripts/export_openapi.py` (`sys.path.insert(0, ...)`)
- Modify tests: `tests/test_error_handling.py`, `tests/test_health.py`, `tests/identity/test_project_endpoints.py`
- Regenerate: `packages/api-client/src/schema.ts` (+ `openapi.json`)

**Interfaces:**
- Consumes: Task 4's routers (all domain errors already return `error_body`).
- Produces:
  - All 4xx/5xx bodies use `{"error": {"code", "message"}}`; HTTP exceptions produce `code="http_<status>"`, validation failures `code="validation_error"` (no echoed input).
  - `GET /api/health` returns 503 `database_unavailable` when the DB is down.
  - `GET /api/projects?limit=&offset=` with `limit` 1..100 (default 50), `offset` >= 0 (default 0).
  - `ListProjects.execute(user_id: str, limit: int = 50, offset: int = 0)`, `ProjectRepository.list_by_user(user_id: str, limit: int = 50, offset: int = 0)`.
  - `get_settings()` cached via `lru_cache`.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_error_handling.py`:

```python
import json


def test_http_exception_uses_the_shared_error_body(client):
    response = client.get("/api/projects")  # no bearer token -> HTTPBearer 401

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "http_401"
    assert "detail" not in body


def test_validation_error_uses_the_shared_error_body_without_echoing_input(client):
    response = client.post(
        "/api/auth/register", json={"email": "not-an-email", "password": "short"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "not-an-email" not in json.dumps(body)
    assert "short" not in json.dumps(body)
```

Add to `tests/test_health.py`:

```python
def test_health_returns_503_when_database_is_unavailable(client):
    from sqlalchemy.exc import OperationalError

    from src.shared_kernel.db import get_db

    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("down"))

    client.app.dependency_overrides[get_db] = lambda: _BrokenSession()

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
```

Add to `tests/identity/test_project_endpoints.py`:

```python
def test_list_projects_supports_limit_and_offset(client):
    token = _register_and_login(client, email="pagination@example.com")
    headers = _auth_headers(token)
    for index in range(3):
        client.post(
            "/api/projects",
            json={"name": f"P{index}", "sql": "...", "dialect": "postgres"},
            headers=headers,
        )

    first_page = client.get("/api/projects?limit=2", headers=headers)
    second_page = client.get("/api/projects?limit=2&offset=2", headers=headers)

    assert len(first_page.json()) == 2
    assert len(second_page.json()) == 1


def test_list_projects_rejects_invalid_pagination(client):
    token = _register_and_login(client, email="bad-pagination@example.com")

    response = client.get("/api/projects?limit=0", headers=_auth_headers(token))

    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_error_handling.py tests/test_health.py tests/identity/test_project_endpoints.py -q` (workdir `apps/api`)
Expected: FAIL — 401 body has `detail`, health returns 500, pagination params ignored.

- [ ] **Step 3: Register the exception handlers**

`apps/api/src/main.py` — add imports and handlers inside `create_app` before `return app`:

```python
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
```

```python
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Log structural fields only: exc.errors() includes the submitted input, which
        # may contain passwords or tokens. Never write those to logs.
        logger.info(
            "request validation failed: %s",
            [{"loc": error.get("loc"), "type": error.get("type")} for error in exc.errors()],
        )
        return JSONResponse(
            status_code=422,
            content=error_body("validation_error", "Request validation failed"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(f"http_{exc.status_code}", detail),
            headers=getattr(exc, "headers", None),
        )
```

- [ ] **Step 4: Health 503 + settings cache + misc**

`health/interfaces.py`:

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.shared_kernel.db import get_db
from src.shared_kernel.errors import error_body

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str


@router.get("/health")
def get_health(db: Session = Depends(get_db)):  # noqa: B008
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content=error_body("database_unavailable", "Database is unavailable"),
        )
    return HealthResponse(status="ok", db="ok")
```

`shared_kernel/settings.py`:

```python
from functools import lru_cache
...
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`shared_kernel/errors.py`: `def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:`

`alembic/env.py` and `scripts/export_openapi.py`: change `sys.path.append(...)` to `sys.path.insert(0, ...)`.

- [ ] **Step 5: Projects pagination**

`project_repository.py`:

```python
    def list_by_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Project]:
        models = (
            self._session.query(ProjectModel)
            .filter_by(user_id=user_id)
            .order_by(ProjectModel.created_at)
            .limit(limit)
            .offset(offset)
            .all()
        )
        return [self._to_domain(m) for m in models]
```

`project_use_cases.py`:

```python
    def execute(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Project]:
        return self._project_repository.list_by_user(user_id, limit=limit, offset=offset)
```

`projects_router.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
```

```python
@router.get("", response_model=list[ProjectSummaryResponse])
def list_projects(
    user_id: str = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),  # noqa: B008
):
    projects = ListProjects(ProjectRepository(db)).execute(user_id, limit=limit, offset=offset)
    return [
        ProjectSummaryResponse(id=p.id, name=p.name, dialect=p.dialect, updated_at=p.updated_at)
        for p in projects
    ]
```

Also annotate `_to_response(project: Project) -> ProjectResponse` and import `Project` from `src.identity.domain.project`.

- [ ] **Step 6: Run tests**

Run: `pytest -q` (workdir `apps/api`)
Expected: all pass (~115 tests).

- [ ] **Step 7: Regenerate client + lint/format + commit**

```powershell
cd apps/api; python scripts/export_openapi.py; cd ..\..\packages\api-client; pnpm generate
```

```bash
ruff check .; ruff format --check .   # from apps/api
git add apps/api/src apps/api/tests apps/api/alembic apps/api/scripts packages/api-client/src/schema.ts packages/api-client/openapi.json
git commit -m "fix(api): unify error envelope, health 503, paginated projects, cached settings"
```

---

### Task 6: Timezone-aware timestamps + migration

**Files:**
- Create: `apps/api/src/shared_kernel/datetimes.py`
- Create: `apps/api/alembic/versions/f3a9c2d41b57_align_timestamp_columns_with_timezone.py`
- Modify: `apps/api/src/identity/infrastructure/models.py`
- Modify: `apps/api/src/identity/infrastructure/refresh_token_repository.py`
- Modify tests: new `tests/shared_kernel/test_datetimes.py`, `tests/identity/test_models_timezone.py`

**Interfaces:**
- Consumes: Task 4's `_as_utc` helper (gets moved here).
- Produces:
  - `shared_kernel.datetimes.utc_now() -> datetime` (aware UTC)
  - `shared_kernel.datetimes.ensure_utc(value: datetime) -> datetime` (adds UTC when naive — SQLite reads)
  - All identity timestamp columns are `DateTime(timezone=True)` in both models and migrations.

- [ ] **Step 1: Write failing tests**

Create `apps/api/tests/shared_kernel/test_datetimes.py`:

```python
from datetime import UTC, datetime

from src.shared_kernel.datetimes import ensure_utc, utc_now


def test_utc_now_is_timezone_aware():
    assert utc_now().tzinfo is UTC


def test_ensure_utc_adds_utc_to_naive_values():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    assert ensure_utc(naive).tzinfo is UTC


def test_ensure_utc_leaves_aware_values_unchanged():
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert ensure_utc(aware) is aware
```

Create `apps/api/tests/identity/test_models_timezone.py`:

```python
from sqlalchemy import DateTime

from src.identity.infrastructure.models import ProjectModel, RefreshTokenModel, UserModel


def test_identity_timestamp_columns_are_timezone_aware():
    for model in (UserModel, ProjectModel, RefreshTokenModel):
        for column in model.__table__.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone is True, f"{model.__name__}.{column.name}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/shared_kernel/test_datetimes.py tests/identity/test_models_timezone.py -q` (workdir `apps/api`)
Expected: FAIL (module missing; `timezone` is False).

- [ ] **Step 3: Add the datetime helpers and switch models**

`apps/api/src/shared_kernel/datetimes.py`:

```python
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize datetimes read back from SQLite (which drops tzinfo) to aware UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
```

`models.py`: import `DateTime`, `utc_now`; change every timestamp mapping, e.g.:

```python
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

Apply to: `UserModel.created_at`; `ProjectModel.created_at`, `.updated_at`; `RefreshTokenModel.expires_at`, `.revoked_at`, `.created_at`.

`refresh_token_repository.py`: remove the local `_as_utc` helper added in Task 4 and use `from src.shared_kernel.datetimes import ensure_utc, utc_now`; replace `datetime.now(UTC)` with `utc_now()` and `_as_utc(...)` with `ensure_utc(...)`. Remove `.replace(tzinfo=None)` stripping from `create()` (pass aware values; SQLite drops tzinfo on bind, Postgres stores `timestamptz`):

```python
    def create(self, id: str, user_id: str, token_hash: str, expires_at: datetime) -> None:
        model = RefreshTokenModel(
            id=id, user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        self._session.add(model)
        self._session.commit()
```

- [ ] **Step 4: Add the migration**

Create `apps/api/alembic/versions/f3a9c2d41b57_align_timestamp_columns_with_timezone.py` (down_revision `aaa30108dfdb` — verify with `alembic heads`):

```python
"""align timestamp columns with timezone

Revision ID: f3a9c2d41b57
Revises: aaa30108dfdb
Create Date: 2026-09-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a9c2d41b57"
down_revision: str | Sequence[str] | None = "aaa30108dfdb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = {
    "users": ["created_at"],
    "projects": ["created_at", "updated_at"],
    "refresh_tokens": ["expires_at", "revoked_at", "created_at"],
}


def upgrade() -> None:
    for table, columns in _TABLES.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                type_=sa.DateTime(timezone=True),
                existing_type=sa.DateTime(),
                postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            )


def downgrade() -> None:
    for table, columns in _TABLES.items():
        for column in columns:
            op.alter_column(
                table,
                column,
                type_=sa.DateTime(),
                existing_type=sa.DateTime(timezone=True),
                postgresql_using=f"{column} AT TIME ZONE 'UTC'",
            )
```

- [ ] **Step 5: Run tests + verify migration SQL generation**

Run: `pytest -q` (workdir `apps/api`)
Expected: all pass — SQLite read-back naive values are normalized by `ensure_utc`, aware params still bind fine.

Run: `alembic upgrade head --sql` with a Postgres `DATABASE_URL` set (offline mode; no DB needed) and confirm the `ALTER TABLE ... TYPE TIMESTAMP WITH TIME ZONE` statements appear.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src apps/api/alembic apps/api/tests
git commit -m "fix(db): align identity timestamps to timezone-aware UTC with migration"
```

---

### Task 7: Frontend, tooling, CI, README, openapi.json tracking

**Files:**
- Modify: `apps/web/src/pages/HomePage.tsx`, `HomePage.test.tsx`
- Modify: `packages/api-client/src/health.ts` (AbortSignal support)
- Modify: `apps/web/index.html` (`lang="en"`)
- Delete: `apps/web/postcss.config.mjs`
- Modify: `apps/web/package.json` (`--max-warnings 0`), `packages/ui/package.json` (lint script + eslint devDeps)
- Modify: `package.json` (root `lint` includes ui)
- Modify: `.github/workflows/ci.yml` (ui lint step)
- Modify: `.gitignore` (track `packages/api-client/openapi.json`)
- Modify: `README.md`
- Add: `git add packages/api-client/openapi.json`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `getHealth(options?: { signal?: AbortSignal })` (backwards compatible).
  - HomePage with loading/ok/unreachable states, `aria-live="polite"`, retry button, fetch aborted on unmount.
  - `openapi.json` tracked; CI drift check now meaningful for both files.
  - README matches reality (Phase 3 implemented; env vars documented; `JWT_SECRET` >= 32 chars).

- [ ] **Step 1: Update the API client health helper**

`packages/api-client/src/health.ts`:

```ts
import type { paths } from './schema'

export type HealthResponse =
  paths['/api/health']['get']['responses'][200]['content']['application/json']

export async function getHealth(
  options: { signal?: AbortSignal } = {},
): Promise<HealthResponse> {
  const response = await fetch('/api/health', { signal: options.signal })
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }
  return response.json() as Promise<HealthResponse>
}
```

- [ ] **Step 2: Write the failing HomePage test**

Replace `apps/web/src/pages/HomePage.test.tsx` with:

```tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { HomePage } from './HomePage'

describe('HomePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the foundation heading', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', db: 'ok' }) }),
    )
    render(<HomePage />)
    expect(screen.getByRole('heading', { name: /schemio — foundation/i })).toBeInTheDocument()
  })

  it('fetches and displays the API health status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', db: 'ok' }) }),
    )
    render(<HomePage />)
    await waitFor(() => {
      expect(screen.getByText(/api: ok/i)).toBeInTheDocument()
    })
  })

  it('shows the unreachable state and retries on demand', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('network down'))
      .mockResolvedValueOnce({ ok: true, json: async () => ({ status: 'ok', db: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)

    render(<HomePage />)
    const retry = await screen.findByRole('button', { name: /retry/i })
    fireEvent.click(retry)

    await waitFor(() => {
      expect(screen.getByText(/api: ok/i)).toBeInTheDocument()
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm --filter web test` (repo root)
Expected: FAIL — no retry button.

- [ ] **Step 4: Rewrite HomePage**

`apps/web/src/pages/HomePage.tsx`:

```tsx
import { getHealth } from '@schemio/api-client'
import { Placeholder } from '@schemio/ui'
import { useEffect, useState } from 'react'

type ApiStatus = 'checking' | 'ok' | 'unreachable'

export function HomePage() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setApiStatus('checking')
    getHealth({ signal: controller.signal })
      .then((health) => setApiStatus(health.status === 'ok' ? 'ok' : 'unreachable'))
      .catch(() => {
        if (!controller.signal.aborted) setApiStatus('unreachable')
      })
    return () => controller.abort()
  }, [attempt, setApiStatus])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-2">
      <h1 className="text-2xl font-bold">Schemio — Foundation</h1>
      <Placeholder label="packages/ui is linked" />
      <p aria-live="polite">api: {apiStatus}</p>
      {apiStatus === 'unreachable' && (
        <button type="button" onClick={() => setAttempt((current) => current + 1)}>
          Retry
        </button>
      )}
    </main>
  )
}
```

- [ ] **Step 5: Tooling + CI + docs**

- `apps/web/index.html`: `lang="en"` (all copy is English).
- Delete `apps/web/postcss.config.mjs` (empty leftover; Tailwind v4 is wired through the Vite plugin).
- `apps/web/package.json`: `"lint": "eslint . --max-warnings 0"`.
- `packages/ui/package.json`: add `"lint": "eslint src --max-warnings 0"` and devDeps `"eslint": "^9.0.0"`, `"eslint-plugin-react-hooks": "^5.0.0"`, `"eslint-plugin-jsx-a11y": "^6.10.0"` (same ranges as web).
- Root `package.json`: `"lint": "biome check . && pnpm --filter web lint && pnpm --filter @schemio/ui lint"`.
- `.github/workflows/ci.yml` web job: add `- run: pnpm --filter @schemio/ui lint` after the web lint step. Run `pnpm install` to update the lockfile for the new ui devDeps (commit `pnpm-lock.yaml`).
- `.gitignore`: delete the `packages/api-client/openapi.json` line.
- `git add packages/api-client/openapi.json` (it exists locally from Task 3/5 regeneration).

README edits:
- Replace the "Status atual" section to say Phase 3 is implemented: `POST /api/schema/parse` (multi-dialect SQL parsing, relationships, warnings), JWT auth (`/api/auth/*`), saved projects (`/api/projects`), and that the diagram UI is Phase 4.
- Setup: document the required `apps/api/.env` keys:

```bash
DATABASE_URL=postgresql://user:pass@host/db
JWT_SECRET=at-least-32-characters-long-secret
CORS_ALLOW_ORIGINS=["http://localhost:5173"]
```

- Add `cd apps/api && alembic upgrade head` to the setup steps.
- Keep the "Updating the generated API client" section (now fully true since `openapi.json` is tracked).

- [ ] **Step 6: Run web + ui lint/tests/build**

Run: `pnpm install; pnpm --filter web lint; pnpm --filter @schemio/ui lint; pnpm --filter web test; pnpm --filter @schemio/ui test; pnpm --filter web build; pnpm exec biome check .`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add apps/web packages/ui packages/api-client package.json pnpm-lock.yaml .github .gitignore README.md packages/api-client/openapi.json
git commit -m "chore(web,ci,docs): a11y and retry states, ui lint in CI, track openapi.json, refresh README"
```

---

### Task 8: Whole-branch verification and PR

**Files:** none (verification only).

- [ ] **Step 1: Run the exact CI commands locally**

```powershell
# web job
pnpm install --frozen-lockfile
pnpm exec biome check .
pnpm --filter web lint
pnpm --filter @schemio/ui lint
pnpm --filter web test
pnpm --filter @schemio/ui test
pnpm --filter web build

# api job (env vars set)
cd apps/api; ruff check .; ruff format --check .; pytest -v

# api-client-schema job
python scripts/export_openapi.py
cd ..\..\packages\api-client; pnpm generate
git diff --exit-code packages/api-client/src/schema.ts packages/api-client/openapi.json
```

Expected: every command green and no schema drift.

- [ ] **Step 2: Local smoke test of the real app (SQLite)**

```powershell
$env:DATABASE_URL="sqlite:///./smoke.db"; $env:JWT_SECRET="smoke_secret_at_least_32_characters_x"
cd apps/api; alembic upgrade head
# start uvicorn in background, then:
#   GET /api/health -> 200 {"status":"ok","db":"ok"}
#   POST /api/schema/parse {"sql":"CREATE TABLE users (id SERIAL PRIMARY KEY);","dialect":"postgres"} -> 200
#   POST /api/auth/register -> 201
# stop server, delete smoke.db
```

Expected: all three responses as above. This proves the ASGI app boots and the health path works with migrations applied.

- [ ] **Step 3: Review the diff against the review findings**

Run: `git log --oneline main..HEAD; git diff main...HEAD --stat`
Confirm every blocking/important finding from the session review is either fixed here or listed under "Out of scope" in the PR body (rate limiting, multi-schema table qualification, access-token revocation on logout, per-repository commit/unit-of-work refactor, expired refresh-token cleanup job, CORS headers on unhandled 500s, shared vitest config).

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin fix/review-findings
gh pr create --title "fix: harden deploy manifest, SQL parser, auth and DB timestamps (review findings)" --body "<summary + findings addressed + out-of-scope list + test plan: the CI command list from Step 1 and smoke test from Step 2>"
```

- [ ] **Step 5: Report back**

Tell the user: PR URL, that Vercel auto-deploys `main` after merge (production `/api/health` should be re-checked then), and the list of deliberately out-of-scope items so they can prioritize them next.

---

