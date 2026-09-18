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
