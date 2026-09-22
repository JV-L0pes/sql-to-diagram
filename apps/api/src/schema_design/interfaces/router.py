import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlglot.errors import SqlglotError

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

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _invalid_sql(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_body("invalid_sql", _ANSI_ESCAPE_RE.sub("", message)),
    )


@router.post("/parse", response_model=ParseSchemaResponse)
def parse_schema(request: ParseSchemaRequest) -> ParseSchemaResponse:
    if not request.sql.strip():
        return _invalid_sql("SQL input is empty.")

    try:
        dialect = SqlDialect.from_string(request.dialect)
    except InvalidDialectError as exc:
        return JSONResponse(status_code=400, content=error_body("invalid_dialect", str(exc)))

    try:
        result = parse_sql_schema(request.sql, dialect)
    except RecursionError:
        return _invalid_sql("SQL nesting is too deep.")
    except (SqlglotError, ValueError) as exc:
        return _invalid_sql(str(exc))

    response = ParseSchemaResponse(
        tables=[
            TableResponse(
                name=table.name,
                columns=[
                    ColumnResponse(
                        name=c.name,
                        type=c.type,
                        nullable=c.nullable,
                        primary_key=c.primary_key,
                        unique=c.unique,
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
                type=r.type,
                source=r.source,
                via_table=r.via_table,
            )
            for r in result.relationships
        ],
        warnings=[
            WarningResponse(code=w.code, table=w.table, message=w.message) for w in result.warnings
        ],
    )
    return response
