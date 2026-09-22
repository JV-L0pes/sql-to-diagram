from collections.abc import Callable
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy import DateTime, Integer, String, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, Session, mapped_column

from src.shared_kernel.datetimes import utc_now
from src.shared_kernel.db import Base, get_db

_LAST_CLEANUP = datetime.min


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counters"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitRepository:
    def __init__(self, session: Session):
        self._session = session

    def hit(self, key: str, window_start: datetime) -> int:
        dialect = self._session.get_bind().dialect.name
        if dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert

        statement = (
            insert(RateLimitCounter)
            .values(key=key, window_start=window_start, count=1)
            .on_conflict_do_update(
                index_elements=["key", "window_start"],
                set_={"count": RateLimitCounter.count + 1},
            )
            .returning(RateLimitCounter.count)
        )
        count = self._session.execute(statement).scalar_one()
        self._session.commit()
        return int(count)

    def delete_older_than(self, cutoff: datetime) -> None:
        self._session.execute(
            delete(RateLimitCounter).where(RateLimitCounter.window_start < cutoff)
        )
        self._session.commit()


def rate_limit(bucket: str, limit: int, window_seconds: int) -> Callable:
    """Fixed-window per-IP limiter backed by the shared database.

    In-memory limiters are per-instance on serverless and give false confidence;
    the Postgres/Neon database the app already uses is free shared state.
    """

    def dependency(request: Request, db: Session = Depends(get_db)):  # noqa: B008
        global _LAST_CLEANUP
        now = utc_now()
        window_start = (now - timedelta(seconds=now.timestamp() % window_seconds)).replace(
            microsecond=0
        )
        repository = RateLimitRepository(db)
        try:
            count = repository.hit(f"{bucket}:{client_ip(request)}", window_start)
            if now.replace(tzinfo=None) - _LAST_CLEANUP > timedelta(hours=1):
                repository.delete_older_than(now - timedelta(days=1))
                _LAST_CLEANUP = now.replace(tzinfo=None)
        except SQLAlchemyError:
            return  # fail-open: a limiter outage must not take the API down
        if count > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(window_seconds)},
            )

    return dependency
