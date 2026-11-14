from types import SimpleNamespace

import pytest

from shortener_app import url_checks
from shortener_app.url_checks import BlockReason, UnsafeURLError, check_local_rules


@pytest.fixture(autouse=True)
def fake_base_url(monkeypatch):
    # Pretend the site runs on revel.io, whatever .env or CI says
    monkeypatch.setattr(
        url_checks, "get_settings", lambda: SimpleNamespace(base_url="https://revel.io")
    )


@pytest.mark.parametrize(
    "url", ["https://example.com/page", "http://93.184.215.14/", "https://notbit.ly/"]
)
def test_allowed(url):
    check_local_rules(url)  # no exception = allowed


@pytest.mark.parametrize(
    "url, reason",
    [
        ("ftp://example.com/file", BlockReason.UNSUPPORTED_SCHEME),
        ("https://user@example.com/", BlockReason.UNSAFE),
        ("http://127.0.0.1/", BlockReason.LOCAL_ADDRESS),
        ("http://192.168.1.1/admin", BlockReason.LOCAL_ADDRESS),
        ("http://app.localhost/", BlockReason.LOCAL_ADDRESS),
        ("https://revel.io/ABCDE", BlockReason.SELF_LINK),
        ("https://bit.ly/xyz", BlockReason.SHORTENER),
        ("https://www.bit.ly/xyz", BlockReason.SHORTENER),
    ],
)
def test_blocked(url, reason):
    with pytest.raises(UnsafeURLError) as exc_info:
        check_local_rules(url)
    assert exc_info.value.reason == reason
