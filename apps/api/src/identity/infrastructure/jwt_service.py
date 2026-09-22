import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: str
    jti: str
    expires_at: datetime


class JwtService:
    def __init__(self, secret: str, expiry_minutes: int = 30):
        self._secret = secret
        self._expiry_minutes = expiry_minutes
        self._algorithm = "HS256"

    def create_access_token(self, user_id: str) -> str:
        expires_at = datetime.now(UTC) + timedelta(minutes=self._expiry_minutes)
        payload = {"sub": user_id, "exp": expires_at, "jti": str(uuid.uuid4())}
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> AccessTokenClaims:
        payload = jwt.decode(
            token,
            self._secret,
            algorithms=[self._algorithm],
            options={"require": ["sub", "exp", "jti"]},
        )
        return AccessTokenClaims(
            user_id=payload["sub"],
            jti=payload["jti"],
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
