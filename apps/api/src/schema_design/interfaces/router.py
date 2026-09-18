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


@router.post("/parse", response_model=ParseSchemaResponse)
def parse_schema(request: ParseSchemaRequest) -> ParseSchemaResponse:
    try:
        dialect = SqlDialect.from_string(request.dialect)
    except InvalidDialectError as exc:
        return JSONResponse(status_code=400, content=error_body("invalid_dialect", str(exc)))

    try:
        result = parse_sql_schema(request.sql, dialect)
    except (ParseError, ValueError) as exc:
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
            WarningResponse(code=w.code.value, table=w.table, message=w.message)
            for w in result.warnings
        ],
    )
    return response
