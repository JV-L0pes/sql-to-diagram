from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.identity.infrastructure.models import RefreshTokenModel


@dataclass(frozen=True)
class RefreshTokenRecord:
    id: str
    user_id: str
    expires_at: datetime


class RotationOutcome(StrEnum):
    ROTATED = "rotated"
    INVALID = "invalid"
    REUSED = "reused"


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


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

    def rotate(
        self,
        old_token_hash: str,
        new_id: str,
        new_token_hash: str,
        new_expires_at: datetime,
    ) -> tuple[RotationOutcome, str | None]:
        """Atomically revoke the old token and issue a replacement.

        Returns (ROTATED, user_id) on success. A revoked token being presented again
        (REUSED) revokes every active token of that user in the same transaction
        (stolen-token defense). FOR UPDATE serializes concurrent rotations on Postgres;
        SQLite (tests) ignores it.
        """
        now = datetime.now(UTC)
        model = (
            self._session.query(RefreshTokenModel)
            .filter(RefreshTokenModel.token_hash == old_token_hash)
            .with_for_update()
            .first()
        )
        if model is None or _as_utc(model.expires_at) <= now:
            return RotationOutcome.INVALID, None
        if model.revoked_at is not None:
            self._revoke_all_for_user_in_transaction(model.user_id, now)
            self._session.commit()
            return RotationOutcome.REUSED, None

        model.revoked_at = now
        self._session.add(
            RefreshTokenModel(
                id=new_id,
                user_id=model.user_id,
                token_hash=new_token_hash,
                expires_at=new_expires_at,
            )
        )
        self._session.commit()
        return RotationOutcome.ROTATED, model.user_id

    def revoke_all_for_user(self, user_id: str) -> None:
        self._revoke_all_for_user_in_transaction(user_id, datetime.now(UTC))
        self._session.commit()

    def _revoke_all_for_user_in_transaction(self, user_id: str, now: datetime) -> None:
        self._session.query(RefreshTokenModel).filter(
            RefreshTokenModel.user_id == user_id,
            RefreshTokenModel.revoked_at.is_(None),
        ).update({"revoked_at": now})
