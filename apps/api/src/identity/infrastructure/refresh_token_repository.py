from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.identity.infrastructure.models import RefreshTokenModel


@dataclass(frozen=True)
class RefreshTokenRecord:
    id: str
    user_id: str
    expires_at: datetime


class RefreshTokenRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(self, id: str, user_id: str, token_hash: str, expires_at: datetime) -> None:
        model = RefreshTokenModel(
            id=id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at.replace(tzinfo=None)
            if expires_at.tzinfo is not None
            else expires_at,
        )
        self._session.add(model)
        self._session.commit()

    def get_valid_by_hash(self, token_hash: str) -> RefreshTokenRecord | None:
        now = datetime.now(UTC).replace(tzinfo=None)
        model = (
            self._session.query(RefreshTokenModel)
            .filter(
                and_(
                    RefreshTokenModel.token_hash == token_hash,
                    RefreshTokenModel.revoked_at.is_(None),
                    RefreshTokenModel.expires_at > now,
                )
            )
            .first()
        )
        if model is None:
            return None
        return RefreshTokenRecord(id=model.id, user_id=model.user_id, expires_at=model.expires_at)

    def revoke(self, token_id: str) -> None:
        model = self._session.get(RefreshTokenModel, token_id)
        if model is not None:
            model.revoked_at = datetime.now(UTC).replace(tzinfo=None)
            self._session.commit()
