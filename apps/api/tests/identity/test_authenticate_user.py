import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.application.authenticate_user import AuthenticateUser
from src.identity.application.register_user import RegisterUser
from src.identity.domain.errors import InvalidCredentialsError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.identity.infrastructure.user_repository import UserRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _register(session, email="a@example.com", password="correct horse battery staple"):
    RegisterUser(UserRepository(session), PasswordHasher()).execute(email, password)


def _make_use_case(session):
    return AuthenticateUser(
        UserRepository(session),
        PasswordHasher(),
        JwtService(secret="test-secret"),
        RefreshTokenRepository(session),
    )


def test_returns_a_token_pair_for_correct_credentials():
    session = _make_session()
    _register(session)
    use_case = _make_use_case(session)

    tokens = use_case.execute("a@example.com", "correct horse battery staple")

    assert tokens.access_token
    assert tokens.refresh_token


def test_rejects_wrong_password():
    session = _make_session()
    _register(session)
    use_case = _make_use_case(session)

    with pytest.raises(InvalidCredentialsError):
        use_case.execute("a@example.com", "wrong password")


def test_rejects_unknown_email():
    session = _make_session()
    use_case = _make_use_case(session)

    with pytest.raises(InvalidCredentialsError):
        use_case.execute("missing@example.com", "anything")
