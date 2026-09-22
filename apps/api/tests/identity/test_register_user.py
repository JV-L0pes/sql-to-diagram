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
