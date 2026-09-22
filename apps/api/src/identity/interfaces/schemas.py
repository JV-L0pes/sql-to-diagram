from datetime import datetime

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class RegisterResponse(BaseModel):
    id: str
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ProjectCreateRequest(BaseModel):
    name: str
    sql: str
    dialect: str


class ProjectUpdateRequest(BaseModel):
    name: str
    sql: str
    dialect: str


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
