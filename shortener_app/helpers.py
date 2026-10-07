from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.datastructures import URL
from pydantic import ValidationError

from . import models, schemas
from .config import get_settings
from .database import SessionLocal


# Friendly messages for Pydantic validation errors, keyed by (field, error type).
# field None means "any field". {placeholders} are filled from the error's ctx,
# so limits like min_length are only written once, in the schema.
FRIENDLY_ERRORS = {
    ("username", "string_too_short"):        "Username must be at least {min_length} characters.",
    ("username", "string_too_long"):         "Username can be at most {max_length} characters.",
    ("username", "string_pattern_mismatch"): "Username can only contain lowercase letters, digits and _.",
    ("email", "value_error"):                "Please enter a valid email address.",
    # password is a SecretStr: its length errors use the generic too_short/too_long
    # types instead of string_too_short/string_too_long.
    ("password", "too_short"):               "Password must be at least {min_length} characters.",
    ("password", "too_long"):                "Password can be at most {max_length} characters.",
    (None, "missing"):                       "Please fill in all required fields.",
}

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DBSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DBSession) -> models.User | None:
    user_id = request.session.get("user_id")
    return db.get(models.User, user_id) if user_id else None

CurrentUser = Annotated[models.User | None, Depends(get_current_user)]


def get_admin_info(request: Request, db_url: models.URL) -> schemas.URLInfo:
    base_url = URL(get_settings().base_url)
    admin_endpoint = request.app.url_path_for(
        "admin_info", secret_key=db_url.secret_key
    )
    db_url.url = str(base_url.replace(path=db_url.key))
    db_url.admin_url = str(base_url.replace(path=admin_endpoint))
    return db_url


def log_in(request: Request, user: models.User):
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["username"] = user.username


def raise_not_found(request):
    message = f"URL '{request.url}' doesn't exist"
    raise HTTPException(status_code=404, detail=message)


def validation_error(e: ValidationError) -> str:
    """Turn the first validation error into a message for users."""
    error = e.errors()[0]
    field = error["loc"][0] if error["loc"] else None
    template = (
        FRIENDLY_ERRORS.get((field, error["type"]))
        or FRIENDLY_ERRORS.get((None, error["type"]))
    )
    if template is None:
        return error["msg"]
    return template.format(**error.get("ctx", {}))