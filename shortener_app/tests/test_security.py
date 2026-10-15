import pytest

from shortener_app.security import hash_password, verify_password

PASSWORD = "correct-horse-battery"


@pytest.fixture
def hashed():
    return hash_password(PASSWORD)


def test_verify_password_correct(hashed):
    assert verify_password(password=PASSWORD, hashed=hashed)


@pytest.mark.parametrize(
    "wrong", ["wrong-password", "Correct-Horse-Battery", "correct-horse-battery ", ""]
)
def test_verify_password_wrong(hashed, wrong):
    assert not verify_password(password=wrong, hashed=hashed)


def test_no_password_in_hash(hashed):
    assert PASSWORD not in hashed


def test_same_pass_different_hash():
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)

    assert first != second
    assert verify_password(password=PASSWORD, hashed=first)
    assert verify_password(password=PASSWORD, hashed=second)


@pytest.mark.parametrize("password", ["пароль-123", "contraseña-ñ", "🔑🔑🔑🔑🔑🔑🔑🔑"])
def test_non_ascii_password(password):
    assert verify_password(password, hash_password(password))
