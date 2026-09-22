import uuid

from sqlalchemy.exc import IntegrityError

from src.identity.domain.errors import EmailAlreadyRegisteredError
from src.identity.domain.user import User
from src.identity.infrastructure.password_hasher import PasswordHasher
from src.identity.infrastructure.user_repository import UserRepository


class RegisterUser:
    def __init__(self, user_repository: UserRepository, password_hasher: PasswordHasher):
        self._user_repository = user_repository
        self._password_hasher = password_hasher

    def execute(self, email: str, password: str) -> User:
        normalized_email = email.strip().lower()
        if self._user_repository.get_by_email(normalized_email) is not None:
            raise EmailAlreadyRegisteredError(normalized_email)

        password_hash = self._password_hasher.hash(password)
        try:
            return self._user_repository.create(
                id=str(uuid.uuid4()), email=normalized_email, password_hash=password_hash
            )
        except IntegrityError as exc:
            # Lost the check-then-create race: the unique constraint is the source of truth.
            raise EmailAlreadyRegisteredError(normalized_email) from exc
