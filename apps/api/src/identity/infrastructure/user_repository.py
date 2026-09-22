from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.identity.domain.user import User
from src.identity.infrastructure.models import UserModel


class UserRepository:
    def __init__(self, session: Session):
        self._session = session

    def create(self, id: str, email: str, password_hash: str) -> User:
        model = UserModel(id=id, email=email, password_hash=password_hash)
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        self._session.refresh(model)
        return self._to_domain(model)

    def get_by_email(self, email: str) -> User | None:
        model = self._session.query(UserModel).filter_by(email=email).first()
        return self._to_domain(model) if model else None

    def get_by_id(self, user_id: str) -> User | None:
        model = self._session.get(UserModel, user_id)
        return self._to_domain(model) if model else None

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            password_hash=model.password_hash,
            created_at=model.created_at,
        )
