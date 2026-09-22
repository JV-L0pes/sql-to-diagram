from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from src.schema_design.domain.dialect import SqlDialect


class RegisterRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    id: str
    email: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


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


class ProjectSummaryResponse(BaseModel):
    id: str
    name: str
    dialect: str
    updated_at: datetime


class ProjectResponse(BaseModel):
    id: str
    name: str
    sql: str
    dialect: str
    created_at: datetime
    updated_at: datetime
