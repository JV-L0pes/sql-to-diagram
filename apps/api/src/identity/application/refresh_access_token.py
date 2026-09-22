import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from src.identity.application.authenticate_user import TokenPair
from src.identity.domain.errors import InvalidRefreshTokenError
from src.identity.infrastructure.jwt_service import JwtService
from src.identity.infrastructure.refresh_token_repository import (
    RefreshTokenRepository,
    RotationOutcome,
)


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
        old_token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        new_raw_token = secrets.token_urlsafe(32)
        new_token_hash = hashlib.sha256(new_raw_token.encode()).hexdigest()

        outcome, user_id = self._refresh_token_repository.rotate(
            old_token_hash=old_token_hash,
            new_id=str(uuid.uuid4()),
            new_token_hash=new_token_hash,
            new_expires_at=datetime.now(UTC) + timedelta(days=self._refresh_token_expiry_days),
        )
        if outcome is not RotationOutcome.ROTATED or user_id is None:
            raise InvalidRefreshTokenError()

        access_token = self._jwt_service.create_access_token(user_id)
        # Opportunistic cleanup keeps the token table bounded without a scheduler.
        self._refresh_token_repository.delete_expired(datetime.now(UTC))
        return TokenPair(access_token=access_token, refresh_token=new_raw_token)
