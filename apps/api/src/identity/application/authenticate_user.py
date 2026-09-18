import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.identity.domain.errors import InvalidCredentialsError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.identity.infrastructure.user_repository import UserRepository


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class AuthenticateUser:
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        jwt_service: JwtService,
        refresh_token_repository: RefreshTokenRepository,
        refresh_token_expiry_days: int = 30,
    ):
        self._user_repository = user_repository
        self._password_hasher = password_hasher
        self._jwt_service = jwt_service
        self._refresh_token_repository = refresh_token_repository
        self._refresh_token_expiry_days = refresh_token_expiry_days

    def execute(self, email: str, password: str) -> TokenPair:
        user = self._user_repository.get_by_email(email)
        if user is None or not self._password_hasher.verify(user.password_hash, password):
            raise InvalidCredentialsError()

        access_token = self._jwt_service.create_access_token(user.id)
        refresh_token = self._issue_refresh_token(user.id)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    def _issue_refresh_token(self, user_id: str) -> str:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._refresh_token_expiry_days)
        self._refresh_token_repository.create(
            id=str(uuid.uuid4()), user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )
        return raw_token
