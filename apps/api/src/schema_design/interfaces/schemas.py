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
