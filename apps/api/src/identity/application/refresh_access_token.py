import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from src.identity.application.authenticate_user import TokenPair
from src.identity.domain.errors import InvalidRefreshTokenError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository


class RefreshAccessToken:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        jwt_service: JwtService,
        refresh_token_expiry_days: int = 30,
    ):
        self._refresh_token_repository = refresh_token_repository
        self._jwt_service = jwt_service
        self._refresh_token_expiry_days = refresh_token_expiry_days

    def execute(self, raw_refresh_token: str) -> TokenPair:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        record = self._refresh_token_repository.get_valid_by_hash(token_hash)
        if record is None:
            raise InvalidRefreshTokenError()

        self._refresh_token_repository.revoke(record.id)

        access_token = self._jwt_service.create_access_token(record.user_id)
        new_raw_token = secrets.token_urlsafe(32)
        new_token_hash = hashlib.sha256(new_raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self._refresh_token_expiry_days)
        self._refresh_token_repository.create(
            id=str(uuid.uuid4()), user_id=record.user_id, token_hash=new_token_hash, expires_at=expires_at
        )
        return TokenPair(access_token=access_token, refresh_token=new_raw_token)
