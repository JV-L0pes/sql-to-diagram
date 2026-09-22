import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.identity.infrastructure import models  # noqa: F401  (registers tables on Base.metadata)
from src.main import create_app
from src.shared_kernel import rate_limit  # noqa: F401  (registers rate_limit_counters)
from src.shared_kernel.db import Base, get_db
from src.shared_kernel.rate_limit import RateLimitCounter

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(test_engine)
TestSessionLocal = sessionmaker(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    with TestSessionLocal() as cleanup_session:
        cleanup_session.query(RateLimitCounter).delete()
        cleanup_session.commit()
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)
