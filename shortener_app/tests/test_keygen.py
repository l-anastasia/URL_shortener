import string

import pytest

from shortener_app.keygen import KEY_LENGTH, create_random_key


@pytest.mark.parametrize("length", [5, 8, 20])
def test_create_random_key(length):
    assert len(create_random_key(length=length)) == length


def test_create_random_key_default():
    assert len(create_random_key()) == KEY_LENGTH


def test_create_random_key_allowed_chars():
    key = create_random_key(length=100)
    assert set(key) <= set(string.ascii_uppercase + string.digits)


def test_create_random_key_is_random():
    keys = {create_random_key() for _ in range(100)}
    assert len(keys) > 1
