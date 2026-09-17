from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared_kernel.db import get_db

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    db: str


@router.get("/health")
def get_health(db: Session = Depends(get_db)) -> HealthResponse:  # noqa: B008
    db.execute(text("SELECT 1"))
    return HealthResponse(status="ok", db="ok")
