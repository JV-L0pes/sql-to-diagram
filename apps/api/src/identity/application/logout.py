import hashlib

from src.identity.infrastructure.refresh_token_repository import RefreshTokenRepository


class Logout:
    def __init__(self, refresh_token_repository: RefreshTokenRepository):
        self._refresh_token_repository = refresh_token_repository

    def execute(self, raw_refresh_token: str) -> None:
        token_hash = hashlib.sha256(raw_refresh_token.encode()).hexdigest()
        record = self._refresh_token_repository.get_valid_by_hash(token_hash)
        if record is not None:
            self._refresh_token_repository.revoke(record.id)
