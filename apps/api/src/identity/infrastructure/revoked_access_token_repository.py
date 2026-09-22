from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.identity.infrastructure.models import RevokedAccessTokenModel


class RevokedAccessTokenRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, jti: str, expires_at: datetime) -> None:
        self._session.add(RevokedAccessTokenModel(jti=jti, expires_at=expires_at))
        self._session.commit()

    def is_revoked(self, jti: str) -> bool:
        return self._session.get(RevokedAccessTokenModel, jti) is not None

    def delete_expired(self, now: datetime) -> None:
        self._session.execute(
            delete(RevokedAccessTokenModel).where(RevokedAccessTokenModel.expires_at < now)
        )
        self._session.commit()
