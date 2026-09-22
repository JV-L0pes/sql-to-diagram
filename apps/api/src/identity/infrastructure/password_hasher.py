from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    def __init__(self):
        self._hasher = Argon2Hasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            # VerifyMismatchError subclasses VerificationError; InvalidHashError covers
            # corrupt/unsupported stored hashes. Never leak a 500 for bad stored data.
            return False
