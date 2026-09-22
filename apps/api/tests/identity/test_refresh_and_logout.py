import hashlib
import secrets
from datetime import UTC

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.identity.application.logout import Logout
from src.identity.application.refresh_access_token import RefreshAccessToken
from src.identity.domain.errors import InvalidRefreshTokenError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.shared_kernel.db import Base


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _issue_raw_token(repo, user_id="u1"):
    import uuid
    from datetime import datetime, timedelta

    raw = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    repo.create(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    return raw


def test_refresh_issues_a_new_token_pair_and_revokes_the_old_one():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    raw = _issue_raw_token(repo)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    tokens = use_case.execute(raw)

    assert tokens.access_token
    assert tokens.refresh_token != raw
    # the old token is now revoked — using it again must fail
    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(raw)


def test_refresh_rejects_an_unknown_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute("not-a-real-token")


def test_logout_revokes_a_valid_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    raw = _issue_raw_token(repo)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    Logout(repo).execute(raw)

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(raw)


def test_logout_is_a_no_op_for_an_unknown_token():
    session = _make_session()
    repo = RefreshTokenRepository(session)

    Logout(repo).execute("not-a-real-token")  # must not raise


def test_reusing_a_revoked_token_revokes_the_whole_token_family():
    session = _make_session()
    repo = RefreshTokenRepository(session)
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))
    first = _issue_raw_token(repo)
    other_session_token = _issue_raw_token(repo)
    rotated = use_case.execute(first).refresh_token

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(first)  # replay of the already-rotated token

    # every active token for that user was revoked as a precaution
    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(rotated)
    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(other_session_token)


def test_rotation_rejects_an_expired_token():
    import uuid
    from datetime import datetime, timedelta

    session = _make_session()
    repo = RefreshTokenRepository(session)
    raw = "expired-token"
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    repo.create(
        id=str(uuid.uuid4()),
        user_id="u1",
        token_hash=token_hash,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    use_case = RefreshAccessToken(repo, JwtService(secret="test-secret"))

    with pytest.raises(InvalidRefreshTokenError):
        use_case.execute(raw)
