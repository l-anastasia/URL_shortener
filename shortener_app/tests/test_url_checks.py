import json
import logging
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from pydantic import SecretStr

from shortener_app import url_checks
from shortener_app.url_checks import (
    BlockReason,
    ClaudeVerdict,
    UnsafeURLError,
    check_local_rules,
    check_safe_browsing,
    check_with_claude,
)

TEST_KEY = "test-key"


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    # Pretend the site runs on revel.io with a Google key, whatever .env or CI says
    settings = SimpleNamespace(
        base_url="https://revel.io",
        google_safe_browsing_api_key=SecretStr(TEST_KEY),
        anthropic_api_key=None,
    )
    monkeypatch.setattr(url_checks, "get_settings", lambda: settings)
    claude_client = url_checks._claude_client  # the real one, before a test fakes it
    claude_client.cache_clear()
    yield settings
    claude_client.cache_clear()


class FakeMessages:
    """Stands in for client.messages: records calls, returns or raises result."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def fake_claude(monkeypatch, result):
    """Make check_with_claude talk to a fake client that returns result."""
    messages = FakeMessages(result)
    client = SimpleNamespace(messages=messages)
    monkeypatch.setattr(url_checks, "_claude_client", lambda: client)
    return messages


def claude_says(suspicious):
    return SimpleNamespace(
        stop_reason="end_turn",
        parsed_output=ClaudeVerdict(suspicious=suspicious, reason="test"),
    )


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


# Claude
@pytest.mark.anyio
async def test_claude_suspicious_blocks(monkeypatch):
    fake_claude(monkeypatch, claude_says(suspicious=True))
    with pytest.raises(UnsafeURLError) as exc_info:
        await check_with_claude("https://paypal-login-secure.xyz/verify")
    assert exc_info.value.reason == BlockReason.UNSAFE


@pytest.mark.anyio
async def test_claude_not_suspicious_allows(monkeypatch):
    messages = fake_claude(monkeypatch, claude_says(suspicious=False))
    await check_with_claude("https://github.com/anthropics")  # no exception = allowed

    # The URL reached Claude, inside the <url> tags
    content = messages.calls[0]["messages"][0]["content"]
    assert content == "<url>https://github.com/anthropics</url>"


@pytest.mark.anyio
async def test_claude_refusal_allows(monkeypatch, caplog):
    fake_claude(monkeypatch, SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with caplog.at_level(logging.WARNING, logger="shortener_app.url_checks"):
        await check_with_claude("https://example.com/")  # fail open: no exception
    assert "Claude gave no verdict" in caplog.text


@pytest.mark.anyio
async def test_claude_error_allows(monkeypatch, caplog):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake_claude(monkeypatch, anthropic.APITimeoutError(request=request))
    with caplog.at_level(logging.WARNING, logger="shortener_app.url_checks"):
        await check_with_claude("https://example.com/")  # fail open: no exception
    assert "Claude check failed" in caplog.text


@pytest.mark.anyio
async def test_claude_skipped_without_key():
    # fake_settings has anthropic_api_key=None, and _claude_client isn't faked here
    assert url_checks._claude_client() is None
    await check_with_claude("https://example.com/")  # no exception = skipped
