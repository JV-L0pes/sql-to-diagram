from datetime import UTC, datetime

from src.identity.domain.user import User


def test_user_holds_all_fields():
    now = datetime.now(UTC)
    user = User(id="u1", email="a@example.com", password_hash="hash", created_at=now)

    assert user.id == "u1"
    assert user.email == "a@example.com"
    assert user.password_hash == "hash"
    assert user.created_at == now
