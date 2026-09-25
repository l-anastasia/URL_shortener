import secrets
import string

from sqlalchemy.orm import Session
from . import crud

KEY_LENGTH = 5

def create_random_key(length: int = KEY_LENGTH) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))

def create_unique_random_key(db: Session) -> str:
    key = create_random_key()
    while crud.get_db_url_by_key(db, key):
        key = create_random_key()
    return key