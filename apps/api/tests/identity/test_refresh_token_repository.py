from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _future():
    return datetime.now(timezone.utc) + timedelta(days=30)


def _past():
    return datetime.now(timezone.utc) - timedelta(days=1)


def test_create_then_get_valid_by_hash_returns_the_record():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    repo.create(id="t1", user_id="u1", token_hash="hash1", expires_at=_future())

    record = repo.get_valid_by_hash("hash1")

    assert record is not None
    assert record.id == "t1"
    assert record.user_id == "u1"


def test_get_valid_by_hash_returns_none_for_unknown_hash():
    session = _make_session()
    repo = RefreshTokenRepository(session)

    assert repo.get_valid_by_hash("nonexistent") is None


def test_get_valid_by_hash_returns_none_for_expired_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    repo.create(id="t1", user_id="u1", token_hash="hash1", expires_at=_past())

    assert repo.get_valid_by_hash("hash1") is None


def test_get_valid_by_hash_returns_none_after_revoke():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    repo.create(id="t1", user_id="u1", token_hash="hash1", expires_at=_future())

    repo.revoke("t1")

    assert repo.get_valid_by_hash("hash1") is None
