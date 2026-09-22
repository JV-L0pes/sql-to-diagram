import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.domain.errors import EmailAlreadyRegisteredError
from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_then_get_by_email_returns_the_same_user():
    session = _make_session()
    repo = UserRepository(session)

    created = repo.create(id="u1", email="a@example.com", password_hash="hash")
    found = repo.get_by_email("a@example.com")

    assert found is not None
    assert found.id == created.id
    assert found.email == "a@example.com"
    assert found.password_hash == "hash"


def test_get_by_email_returns_none_when_not_found():
    session = _make_session()
    repo = UserRepository(session)

    assert repo.get_by_email("missing@example.com") is None


def test_get_by_id_returns_the_matching_user():
    session = _make_session()
    repo = UserRepository(session)
    created = repo.create(id="u1", email="a@example.com", password_hash="hash")

    found = repo.get_by_id("u1")

    assert found is not None
    assert found.id == created.id


def test_duplicate_email_create_raises_domain_error():
    session = _make_session()
    repo = UserRepository(session)
    repo.create(id="u1", email="a@example.com", password_hash="hash")

    with pytest.raises(EmailAlreadyRegisteredError):
        repo.create(id="u2", email="a@example.com", password_hash="hash")
