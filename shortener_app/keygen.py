import secrets
import string

from sqlalchemy.ext.asyncio import AsyncSession

from . import crud

KEY_LENGTH = 5


def create_random_key(length: int = KEY_LENGTH) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


async def create_unique_random_key(db: AsyncSession) -> str:
    key = create_random_key()
    while await crud.get_db_url_by_key(db, key):
        key = create_random_key()
    return key
