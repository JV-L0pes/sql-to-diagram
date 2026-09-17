from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shared_kernel.db import get_db

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def get_health(db: Session = Depends(get_db)) -> dict:  # noqa: B008
    db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}
