import asyncio

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import keygen, models, schemas, security


async def create_db_url(
    db: AsyncSession, url: schemas.URLBase, owner_id: int | None = None
) -> models.URL:
    key = await keygen.create_unique_random_key(db)
    secret_key = f"{key}_{keygen.create_random_key(length=8)}"

    db_url = models.URL(
        target_url=url.target_url, key=key, secret_key=secret_key, owner_id=owner_id
    )
    db.add(db_url)
    await db.commit()
    await db.refresh(db_url)
    return db_url


async def get_db_url_by_key(db: AsyncSession, url_key: str) -> models.URL | None:
    return await db.scalar(
        select(models.URL).where(models.URL.key == url_key, models.URL.is_active)
    )


async def get_db_url_by_secret_key(
    db: AsyncSession, secret_key: str
) -> models.URL | None:
    return await db.scalar(
        select(models.URL).where(
            models.URL.secret_key == secret_key, models.URL.is_active
        )
    )


async def update_db_clicks(db: AsyncSession, db_url: models.URL) -> models.URL:
    await db.execute(
        update(models.URL)
        .where(models.URL.id == db_url.id)
        .values(clicks=models.URL.clicks + 1)
    )
    await db.commit()
    await db.refresh(db_url)
    return db_url


async def _deactivate_url(
    db: AsyncSession, db_url: models.URL | None
) -> models.URL | None:
    """Mark link as deleted (soft delete). Does nothing if db_url is None."""
    if db_url:
        db_url.is_active = False
        await db.commit()
        await db.refresh(db_url)
    return db_url


async def deactivate_db_url_by_secret(
    db: AsyncSession, secret_key: str
) -> models.URL | None:
    """Manage page + API: allowed because the caller knows the secret key."""
    db_url = await get_db_url_by_secret_key(db, secret_key=secret_key)
    return await _deactivate_url(db=db, db_url=db_url)


async def deactivate_db_url_by_owner(
    db: AsyncSession, url_key: str, owner_id: int
) -> models.URL | None:
    """Account page: allowed because the logged-in user owns the link."""
    db_url = await db.scalar(
        select(models.URL).where(
            models.URL.key == url_key,
            models.URL.owner_id == owner_id,
            models.URL.is_active,
        )
    )
    return await _deactivate_url(db=db, db_url=db_url)


async def get_user_by_username(db: AsyncSession, username: str) -> models.User | None:
    return await db.scalar(select(models.User).where(models.User.username == username))


async def create_user(db: AsyncSession, user: schemas.UserCreate) -> models.User:
    password_hash = await asyncio.to_thread(
        security.hash_password, user.password.get_secret_value()
    )
    db_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=password_hash,
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def get_user_by_email(db: AsyncSession, email: str) -> models.User | None:
    return await db.scalar(select(models.User).where(models.User.email == email))


async def get_urls_by_owner(db: AsyncSession, owner_id: int) -> list[models.URL]:
    result = await db.scalars(
        select(models.URL)
        .where(models.URL.owner_id == owner_id, models.URL.is_active)
        .order_by(models.URL.created_at.desc())
    )
    return list(result.all())
