# Schema Design Domain — Real SQL Parsing (Phase 2 of 5)

## Context

Phase 1 (Foundation, see `2026-09-16-foundation-design.md`) built the
monorepo skeleton and proved `apps/web` → `apps/api` → Neon works
end-to-end via a trivial `/api/health` slice. The `schema_design` bounded
context in `apps/api` exists only as empty `domain/application/
infrastructure/interfaces` folders plus one real piece of domain code:
`SqlDialect` (a value object with `POSTGRES`/`MYSQL`/`SQLITE`/`MSSQL`
members and `from_string()` validation).

This phase builds the actual product: parsing user-submitted SQL into a
structured schema (tables, columns, relationships) plus structural
modeling warnings, replacing the legacy `src/lib/sqlParser.ts` regex
parser entirely (that file no longer exists — it was deleted in Phase 1
along with the rest of the old Next.js app).

## Goals

- Parse `CREATE TABLE` (and relevant `ALTER TABLE`/`CREATE INDEX`)
  statements across all four dialects `SqlDialect` already models
  (Postgres, MySQL, SQLite, SQL Server) using sqlglot as the parsing
  engine — a single source of truth, no per-dialect regex.
- Detect relationships: explicit (declared `FOREIGN KEY`) and, as a
  fallback when no FK is declared, name-convention-based (e.g.
  `usuario_id` → `usuarios.id`) — clearly tagged so a consumer can tell
  the difference.
- Detect many-to-many relationships through junction tables (a table
  whose primary key is exactly the union of two foreign keys, with no
  other significant columns) — this logic already existed in the legacy
  parser and is worth preserving, now tested.
- Surface structural "modeling warnings": problems detectable from the
  schema alone, not full relational-theory normalization proofs.
- Expose all of this as `POST /api/schema/parse`, a public (no-auth)
  endpoint, matching the Foundation spec's decision that parsing needs
  no login.

## Non-goals (explicitly deferred)

- **Formal 2NF/3NF verification.** Those require known functional
  dependencies between columns, which cannot be reliably inferred from a
  `CREATE TABLE` statement alone (no data, no documented FDs). Claiming
  to check 2NF/3NF from structure alone would be misleading. This phase
  only implements checks that are genuinely verifiable from schema
  structure (see "Structural warnings" below).
- Any frontend UI for this endpoint — Phase 4 builds the SQL editor and
  diagram canvas. This phase is verified via automated tests and, for
  manual spot-checks, FastAPI's auto-generated `/docs` (Swagger UI).
- Auth, saved projects (Phase 3) — the endpoint stays public.
- NoSQL/Mongo (Phase 5) — out of scope entirely.

## Architecture

All new code lives inside the `schema_design` bounded context already
scaffolded in Phase 1 (`apps/api/src/schema_design/`), following its
existing four-layer split:

```
apps/api/src/schema_design/
├── domain/
│   ├── dialect.py          # existing (Phase 1): SqlDialect
│   ├── table.py            # Column, Table
│   ├── relationship.py     # Relationship, RelationshipType, RelationshipSource
│   ├── warning.py          # SchemaWarning, WarningCode
│   └── parsed_schema.py    # ParsedSchema (the aggregate: tables + relationships + warnings)
├── application/
│   └── parse_sql_schema.py # ParseSqlSchema use case
├── infrastructure/
│   ├── sqlglot_parser.py   # translates sqlglot's AST into domain objects (Table/Column)
│   ├── relationship_detector.py   # explicit FK + junction-table + naming-convention inference
│   └── structural_validator.py    # produces SchemaWarning list from a ParsedSchema
└── interfaces/
    ├── schemas.py          # Pydantic request/response models
    └── router.py           # POST /api/schema/parse
```

`domain/` stays free of sqlglot and FastAPI imports, per the Phase 1
constraint — it only knows about `Table`, `Column`, `Relationship`,
`SchemaWarning` as plain dataclasses/value objects and the *rules* for
comparing/validating them (e.g. "is this column unique", "do these two
column types look compatible for a relationship"). `infrastructure/`
is where sqlglot's AST gets walked and translated; if sqlglot's API
changes, only this layer changes.

**Why one aggregate (`ParsedSchema`) instead of returning three separate
lists from the use case:** tables, relationships, and warnings are
produced together from one parse pass and are always consumed together
by the interface layer — bundling them avoids three parallel return
values threading through every layer.

## API Contract

```
POST /api/schema/parse
Content-Type: application/json

{
  "sql": "CREATE TABLE users (...); CREATE TABLE posts (...);",
  "dialect": "postgres"   // one of: postgres | mysql | sqlite | mssql
}
```

**200 OK:**
```json
{
  "tables": [
    {
      "name": "users",
      "columns": [
        {"name": "id", "type": "SERIAL", "nullable": false, "primary_key": true},
        {"name": "email", "type": "VARCHAR(255)", "nullable": false, "primary_key": false}
      ]
    }
  ],
  "relationships": [
    {
      "from_table": "posts", "from_column": "user_id",
      "to_table": "users", "to_column": "id",
      "type": "MANY_TO_ONE",
      "source": "explicit"
    }
  ],
  "warnings": [
    {
      "code": "missing_primary_key",
      "table": "logs",
      "message": "Table 'logs' has no primary key."
    }
  ]
}
```

**400 Bad Request** (invalid SQL, unsupported dialect, or empty input) —
uses the shared `error_body()` shape from `shared_kernel/errors.py`
(already wired to a global exception handler in Phase 1):
```json
{"error": {"code": "invalid_sql", "message": "<sqlglot's parse error, including line/position if available>"}}
```

`dialect` reuses `SqlDialect.from_string()` (already raises
`InvalidDialectError` on bad input, which the router maps to 400 via
the same `error_body` shape — no new error-handling pattern needed).

## Relationship Detection Rules

1. **Explicit**: a declared `FOREIGN KEY (col) REFERENCES table(col)` —
   always `source: "explicit"`. Cardinality (`ONE_TO_ONE` / `ONE_TO_MANY`
   / `MANY_TO_ONE`) is derived from whether the FK column and the
   referenced column are each individually unique (PK or UNIQUE
   constraint), same logic as the legacy parser's
   `determineRelationshipType`, ported and tested.
2. **Many-to-many via junction table**: a table is classified as a
   junction when its primary key is exactly the union of exactly two
   foreign key columns and it has no more than a couple of incidental
   columns (e.g. `created_at`) beyond those FKs — ported from the legacy
   `identifyJunctionTables`/`processManyToManyRelationship` logic. Both
   directions of the resulting `MANY_TO_MANY` relationship are
   `source: "explicit"` (the FKs that produce them are explicit).
3. **Inferred (naming convention)**: only runs for a column that has NO
   explicit FK, matches the pattern `<singular_or_plural_noun>_id`, and a
   table exists whose name plausibly matches that noun (reusing the
   legacy parser's pluralization heuristics: `+s`, `+es`, trailing-`s`
   removal, `+a`/`+as` for Portuguese-style names already in the legacy
   code's test fixtures) AND that table has an `id`-named column of a
   compatible type. Tagged `source: "inferred"`.

## Structural Warnings (not formal normalization)

Each warning has a stable `code` (for a future UI to map to an icon/copy)
and a human-readable `message`:

| Code | Trigger |
|---|---|
| `missing_primary_key` | Table has zero PK columns. |
| `non_atomic_column_type` | Column type is an array type (`ARRAY`, `TEXT[]`, Postgres `_text`, etc.) or a JSON/JSONB type — informational, not necessarily wrong, but flagged as a 1NF-adjacent concern. |
| `nullable_foreign_key` | A column that is part of an explicit FK is nullable — worth surfacing since it changes the relationship's real-world meaning (optional vs mandatory association). |
| `non_snake_case_identifier` | A table or column name isn't `snake_case` (mixed case, spaces via quoting, etc.) — naming-convention consistency, not a correctness bug. |

Warnings never block a successful parse — `tables`/`relationships` are
still returned; `warnings` is simply non-empty. This is why they're a
list on the success response, not a separate error path.

## Error Handling

- Invalid/unparseable SQL: sqlglot raises `sqlglot.errors.ParseError`.
  The `infrastructure/sqlglot_parser.py` layer does not catch it —
  `application/parse_sql_schema.py` lets it propagate, and
  `interfaces/router.py` catches `ParseError` specifically (not a bare
  `except`) and maps it to a 400 with `error_body("invalid_sql", str(exc))`.
  This mirrors the Phase 1 pattern (typed exceptions raised deep, mapped
  to HTTP status at the interface layer) rather than reusing the global
  500 handler, since a parse failure is a client error (bad input), not
  a server fault.
- Invalid dialect string: `SqlDialect.from_string()` already raises
  `InvalidDialectError` (Phase 1) — same 400 treatment.
- No bare `except`/silent fallback anywhere — the legacy parser's
  `catch (error) { console.error(...) }` silently returning an empty
  schema is exactly the bug class this phase eliminates.

## Testing

- **Business-rule tests** (`apps/api/tests/schema_design/`), Given/When/Then
  style, one file per concern: `test_table_extraction.py` (columns,
  types, PK per dialect), `test_relationship_detection.py` (explicit,
  junction/many-to-many, inferred-by-convention, including the
  false-positive-avoidance cases: two columns of incompatible types
  shouldn't infer a relationship), `test_structural_warnings.py` (one
  test per warning code, positive and negative case).
- **Dialect coverage**: the extraction tests run the same scenarios
  (a users/posts/many-to-many fixture) through all four dialects via
  `pytest.mark.parametrize`, asserting dialect-specific type syntax
  (`SERIAL` vs `AUTO_INCREMENT` vs `INTEGER PRIMARY KEY` vs
  `IDENTITY(1,1)`) all normalize to equivalent domain `Table` objects.
- **Integration test**: `test_parse_endpoint.py` hits `POST
  /api/schema/parse` via `TestClient` (no DB involved — this endpoint is
  public and stateless, doesn't touch `get_db` at all) with a real
  multi-table SQL script and asserts the full JSON shape, plus one test
  for the 400 path (malformed SQL) and one for an invalid dialect string.
- No mocking of sqlglot itself — these are real parses of real SQL
  strings, since that's the entire point of the domain under test.

## Key Decisions

- **sqlglot only, no per-dialect libraries.** Already decided in Phase 1
  based on its dialect coverage (including T-SQL, which the legacy
  `sql-parser-cst` dependency couldn't do) and its purpose-built AST for
  extracting DDL metadata.
- **Structural warnings, not formal normalization.** Decided during this
  phase's brainstorm: 2NF/3NF checks would require functional-dependency
  data not present in a schema-only parse, and a "check" that's really a
  guess would be worse than no check. This may be revisited if a future
  phase adds sample-data analysis.
- **Naming-convention relationship inference stays, explicitly tagged.**
  Preserves useful behavior from the legacy parser for schemas without
  declared FKs (common in older MySQL/SQLite scripts) while being honest
  in the API response about confidence level, so a future UI (Phase 4)
  can render inferred relationships differently (e.g. dashed lines).
