import os
import threading
import uuid
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.infrastructure.models import UserModel
from src.identity.infrastructure.refresh_token_repository import (
    RefreshTokenRepository,
    RotationOutcome,
)
from src.shared_kernel.db import Base

TEST_POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL")

pytestmark = pytest.mark.skipif(not TEST_POSTGRES_URL, reason="TEST_POSTGRES_URL not set")


def test_concurrent_rotation_mints_exactly_one_replacement():
    """Real-Postgres check for SELECT ... FOR UPDATE rotation semantics (SQLite ignores locks)."""
    engine = create_engine(TEST_POSTGRES_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    raw = "concurrent-token"
    token_hash = sha256(raw.encode()).hexdigest()
    with session_factory() as setup:
        setup.add(UserModel(id="u1", email="u1@example.com", password_hash="h"))
        setup.commit()
        RefreshTokenRepository(setup).create(
            id=str(uuid.uuid4()),
            user_id="u1",
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )

    barrier = threading.Barrier(2)
    outcomes: list[RotationOutcome] = []
    lock = threading.Lock()

    def rotate_once() -> None:
        session = session_factory()
        try:
            barrier.wait(timeout=10)
            outcome, _ = RefreshTokenRepository(session).rotate(
                old_token_hash=token_hash,
                new_id=str(uuid.uuid4()),
                new_token_hash=str(uuid.uuid4()),
                new_expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        finally:
            session.close()
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=rotate_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert sorted(outcomes) == [RotationOutcome.REUSED, RotationOutcome.ROTATED]
