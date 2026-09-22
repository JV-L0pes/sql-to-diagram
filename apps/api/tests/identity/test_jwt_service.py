from datetime import UTC, datetime

import jwt
import pytest

from src.identity.infrastructure.jwt_service import JwtService


def test_create_then_decode_returns_the_same_user_id():
    service = JwtService(secret="test-secret", expiry_minutes=30)
    token = service.create_access_token("user-123")

    assert service.decode_access_token(token).user_id == "user-123"


def test_decode_rejects_expired_token():
    service = JwtService(secret="test-secret", expiry_minutes=-1)  # already expired
    token = service.create_access_token("user-123")

    with pytest.raises(jwt.ExpiredSignatureError):
        service.decode_access_token(token)


def test_decode_rejects_token_signed_with_a_different_secret():
    service_a = JwtService(secret="secret-a", expiry_minutes=30)
    service_b = JwtService(secret="secret-b", expiry_minutes=30)
    token = service_a.create_access_token("user-123")

    with pytest.raises(jwt.InvalidTokenError):
        service_b.decode_access_token(token)


def test_each_access_token_has_a_unique_jti_and_expiry():
    service = JwtService(secret="test-secret", expiry_minutes=30)
    first = service.decode_access_token(service.create_access_token("u1"))
    second = service.decode_access_token(service.create_access_token("u1"))

    assert first.user_id == "u1"
    assert first.jti and first.jti != second.jti
    assert first.expires_at > datetime.now(UTC)
