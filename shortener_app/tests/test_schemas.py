import pytest
from pydantic import ValidationError
from shortener_app.schemas import URLBase, UserCreate

# URLBase
def test_url_is_stripped():
    assert URLBase(target_url="  https://example.com/page  ").target_url == "https://example.com/page"


@pytest.mark.parametrize("bad_url", ["not a url", "example.com", "http://", ""])
def test_url_is_invalid(bad_url):
    with pytest.raises(ValidationError) as exc_info:
        URLBase(target_url=bad_url)
    assert exc_info.value.errors()[0]["type"] == "invalid_url"


# UserCreate
VALID = {
    "username": "alice_01",
    "email": "alice@gmail.com",
    "password": "plum-orbit-canyon-77",
    "confirm_password": "plum-orbit-canyon-77",
}

def make_user(**changes):
    return UserCreate(**{**VALID, **changes})

def error_type(**changes):
    with pytest.raises(ValidationError) as exc_info:
        make_user(**changes)
    return exc_info.value.errors()[0]["type"]


def test_valid_user():
    assert make_user().username == "alice_01"


@pytest.mark.parametrize("username, expected", [
    ("abcd", "string_too_short"),          # under 5 characters
    ("a" * 16, "string_too_long"),         # over 15
    ("Alice_01", "string_pattern_mismatch"),
    ("alice 01", "string_pattern_mismatch"),
    ("alice-01", "string_pattern_mismatch"),
])
def test_invalid_username(username, expected):
    assert error_type(username=username) == expected


@pytest.mark.parametrize("email", ["", "   ", None])
def test_email_is_none(email):
    assert make_user(email=email).email is None

def test_email_is_lowercased_and_stripped():
    assert make_user(email="  Alice@Gmail.COM ").email == "alice@gmail.com"

def test_email_invalid():
    assert error_type(email="not-an-email") == "value_error"


def test_password_too_short():
    assert error_type(password="Ab1!", confirm_password="Ab1!") == "too_short"

def test_password_contains_username():
    pw = "alice_01-plum-orbit"
    assert error_type(password=pw, confirm_password=pw) == "password_contains_username"

def test_weak_password():
    assert error_type(password="password123", confirm_password="password123") == "weak_password"

def test_passwords_dont_match():
    assert error_type(confirm_password="plum-orbit-canyon-78") == "password_mismatch"