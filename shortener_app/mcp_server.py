from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from . import crud, models, schemas
from .config import get_settings
from .database import SessionLocal

mcp = FastMCP("revelio")


def link_details(db_url: models.URL) -> dict:
    base_url = get_settings().base_url.rstrip("/")
    return {
        "short_url": f"{base_url}/{db_url.key}",
        "target_url": db_url.target_url,
        "clicks": db_url.clicks,
        "is_active": db_url.is_active,
        "created_at": db_url.created_at.isoformat(),
        "key": db_url.key,
        "secret_key": db_url.secret_key,
    }


@mcp.tool()
async def create_short_link(target_url: str) -> dict:
    """Create a short link for a URL.

    Returns the short URL and a secret admin key. The admin key is the only
    way to see stats or delete the link later, so show it to the user.
    """
    try:
        url = schemas.URLBase(target_url=target_url)
    except ValidationError:
        raise ValueError(f"Not a valid URL: {target_url}") from None
    async with SessionLocal() as db:
        db_url = await crud.create_db_url(db=db, url=url)
        return link_details(db_url)


@mcp.tool()
async def lookup_link(key: str) -> dict:
    """Find where a short link key points, without counting a click."""
    async with SessionLocal() as db:
        db_url = await crud.get_db_url_by_key(db=db, url_key=key.strip().upper())
    if not db_url:
        raise ValueError(f"No link with key {key}")
    return {"key": db_url.key, "target_url": db_url.target_url}


@mcp.tool()
async def get_link_info(secret_key: str) -> dict:
    """Get a link's details (target, clicks, creation date) by its admin key."""
    async with SessionLocal() as db:
        db_url = await crud.get_db_url_by_secret_key(
            db, secret_key=secret_key.strip().upper()
        )
    if not db_url:
        raise ValueError("No active link with this admin key")
    return link_details(db_url)


@mcp.tool()
async def delete_link(secret_key: str) -> str:
    """Delete (deactivate) a link by its admin key. This cannot be undone."""
    async with SessionLocal() as db:
        db_url = await crud.deactivate_db_url_by_secret(
            db, secret_key=secret_key.strip().upper()
        )
    if not db_url:
        raise ValueError("No active link with this admin key")
    return f"Deleted the short link for {db_url.target_url}"


if __name__ == "__main__":
    mcp.run()  # stdio is the default transport
