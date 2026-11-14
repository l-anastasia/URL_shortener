import json
import logging
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from shortener_app import url_checks
from shortener_app.url_checks import (
    BlockReason,
    UnsafeURLError,
    check_local_rules,
    check_safe_browsing,
)

TEST_KEY = "test-key"


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    # Pretend the site runs on revel.io with a Google key, whatever .env or CI says
    settings = SimpleNamespace(
        base_url="https://revel.io",
        google_safe_browsing_api_key=SecretStr(TEST_KEY),
    )
    monkeypatch.setattr(url_checks, "get_settings", lambda: settings)
    return settings


def fake_google(monkeypatch, handler):
    """Send the check's HTTP requests to handler instead of the real Google."""
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        url_checks.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )


# Local rules
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


# Google Safe Browsing
@pytest.mark.anyio
async def test_google_match_blocks(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"matches": [{"threatType": "MALWARE"}]})

    fake_google(monkeypatch, handler)
    with pytest.raises(UnsafeURLError) as exc_info:
        await check_safe_browsing("https://evil.example/")
    assert exc_info.value.reason == BlockReason.UNSAFE


@pytest.mark.anyio
async def test_google_no_match_allows(monkeypatch):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json={})

    fake_google(monkeypatch, handler)
    await check_safe_browsing("https://example.com/")  # no exception = allowed

    # The request is the one Google expects, with the key in a header
    request = sent[0]
    assert request.headers["X-Goog-Api-Key"] == TEST_KEY
    assert "key=" not in str(request.url)
    body = json.loads(request.content)
    assert body["threatInfo"]["threatEntries"] == [{"url": "https://example.com/"}]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "outcome",
    [
        httpx.Response(500),
        httpx.Response(200, text="not json"),
        httpx.ConnectTimeout("Google is too slow"),
    ],
    ids=["server-error", "bad-json", "timeout"],
)
async def test_google_failure_allows(monkeypatch, caplog, outcome):
    def handler(request):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    fake_google(monkeypatch, handler)
    with caplog.at_level(logging.WARNING, logger="shortener_app.url_checks"):
        await check_safe_browsing("https://example.com/")  # fail open: no exception
    assert "Safe Browsing check failed" in caplog.text


@pytest.mark.anyio
async def test_google_skipped_without_key(monkeypatch, fake_settings):
    sent = []
    fake_google(monkeypatch, lambda request: sent.append(request))
    fake_settings.google_safe_browsing_api_key = None

    await check_safe_browsing("https://example.com/")
    assert sent == []  # Google was never called
