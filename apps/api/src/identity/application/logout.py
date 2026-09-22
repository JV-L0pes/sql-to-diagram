import hashlib
from datetime import datetime

from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository
from src.identity.infrastructure.revoked_access_token_repository import (
    RevokedAccessTokenRepository,
)
from src.shared_kernel.datetimes import utc_now


class Logout:
    def __init__(
        self,
        refresh_token_repository: RefreshTokenRepository,
        revoked_access_token_repository: RevokedAccessTokenRepository,
    ):
        self._refresh_token_repository = refresh_token_repository
        self._revoked_access_token_repository = revoked_access_token_repository

    def execute(self, raw_refresh_token: str, access_jti: str, access_expires_at: datetime) -> None:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        record = self._refresh_token_repository.get_valid_by_hash(token_hash)
        if record is not None:
            self._refresh_token_repository.revoke(record.id)

        self._revoked_access_token_repository.add(access_jti, access_expires_at)

        now = utc_now()
        self._refresh_token_repository.delete_expired(now)
        self._revoked_access_token_repository.delete_expired(now)
