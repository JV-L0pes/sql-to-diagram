import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.application.register_user import RegisterUser
from src.identity.domain.errors import EmailAlreadyRegisteredError
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_use_case():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    return RegisterUser(UserRepository(session), PasswordHasher())


def test_registers_a_new_user_with_a_hashed_password():
    use_case = _make_use_case()

    user = use_case.execute("a@example.com", "correct horse battery staple")

    assert user.email == "a@example.com"
    assert user.password_hash != "correct horse battery staple"


def test_rejects_a_duplicate_email():
    use_case = _make_use_case()
    use_case.execute("a@example.com", "password1")

    with pytest.raises(EmailAlreadyRegisteredError):
        use_case.execute("a@example.com", "password2")


class _AlwaysMissUserRepository:
    """Simulates losing the check-then-create race: get_by_email misses, insert collides."""

    def __init__(self, real_repository):
        self._real = real_repository

    def get_by_email(self, email):
        return None

    def create(self, **kwargs):
        return self._real.create(**kwargs)


def test_maps_integrity_error_race_to_email_already_registered():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    real = UserRepository(session)
    use_case = RegisterUser(real, PasswordHasher())
    use_case.execute("a@example.com", "correct horse battery staple")

    racing = RegisterUser(_AlwaysMissUserRepository(real), PasswordHasher())
    with pytest.raises(EmailAlreadyRegisteredError):
        racing.execute("A@EXAMPLE.COM", "another password")


def test_email_is_normalized_on_register():
    use_case = _make_use_case()

    user = use_case.execute("  A@Example.COM ", "correct horse battery staple")

    assert user.email == "a@example.com"
