import ipaddress
import logging
from enum import Enum
from urllib.parse import urlsplit

from .config import get_settings

logger = logging.getLogger(__name__)


class BlockReason(Enum):
    UNSUPPORTED_SCHEME = "Only http and https links are supported."
    LOCAL_ADDRESS = "This link points to a private or local address."
    SELF_LINK = "You can't shorten a link that points to this site."
    SHORTENER = (
        "Links to other URL shorteners aren't allowed. "
        "Paste the original link instead."
    )
    UNSAFE = "This link looks unsafe, so we won't shorten it."

class UnsafeURLError(Exception):
    def __init__(self, reason: BlockReason):
        super().__init__(reason.value)   # so str(e) and logs show the reason too
        self.reason = reason


SHORTENER_DOMAINS = frozenset({
    "bit.ly", 
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "is.gd",
    "ow.ly",
    "buff.ly",
    "rebrand.ly",
    "cutt.ly",
    "shorturl.at",
    "tiny.cc",
    "rb.gy",
    }) 


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def check_local_rules(url: str) -> None:
    parts = urlsplit(url)
    host = (parts.hostname or "").rstrip(".")

    if parts.scheme not in {"http", "https"}:
        logger.info("Blocked %s: wrong scheme - %r", url, parts.scheme)
        raise UnsafeURLError(BlockReason.UNSUPPORTED_SCHEME)
    if parts.username is not None:
        logger.info("Blocked %s: URL obfuscation ", url)
        raise UnsafeURLError(BlockReason.UNSAFE)
    if host is None:
        logger.info("Blocked %s: URL obfuscation ", url)
        raise UnsafeURLError(BlockReason.UNSAFE)

    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and not ip.is_global:
        logger.info("Blocked %s: ip is not public - %r", url, ip)
        raise UnsafeURLError(BlockReason.LOCAL_ADDRESS)

    own_host = urlsplit(get_settings().base_url).hostname
    if host == own_host:
        logger.info("Blocked %s: it us - %r", url, host)
        raise UnsafeURLError(BlockReason.SELF_LINK)
    
    if any(_host_matches(host, d) for d in SHORTENER_DOMAINS):
        logger.info("Blocked %s: shortener host %r", url, host)
        raise UnsafeURLError(BlockReason.SHORTENER)

async def check_url(url: str) -> None:
    check_local_rules(url)
    # later: await check_safe_browsing(url), await check_with_llm(url)