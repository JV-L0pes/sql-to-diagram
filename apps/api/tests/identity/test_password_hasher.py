from src.identity.infrastructure.password_hasher import PasswordHasher


def test_hash_then_verify_succeeds_with_correct_password():
    hasher = PasswordHasher()
    password_hash = hasher.hash("correct horse battery staple")

    assert hasher.verify(password_hash, "correct horse battery staple") is True


def test_verify_fails_with_wrong_password():
    hasher = PasswordHasher()
    password_hash = hasher.hash("correct horse battery staple")

    assert hasher.verify(password_hash, "wrong password") is False


def test_hash_is_not_the_plaintext_password():
    hasher = PasswordHasher()
    password_hash = hasher.hash("correct horse battery staple")

    assert password_hash != "correct horse battery staple"
    assert "correct horse battery staple" not in password_hash


def test_verify_returns_false_for_a_corrupt_hash_instead_of_raising():
    hasher = PasswordHasher()

    assert hasher.verify("not-an-argon2-hash", "anything") is False
