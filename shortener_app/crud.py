from sqlalchemy.orm import Session
from . import keygen, models, schemas, security

def create_db_url(db: Session, url: schemas.URLBase, owner_id: int | None = None) -> models.URL:
    key = keygen.create_unique_random_key(db)
    secret_key = f"{key}_{keygen.create_random_key(length=8)}"

    db_url = models.URL(
        target_url=url.target_url, key=key, secret_key=secret_key, owner_id=owner_id
    )
    db.add(db_url)
    db.commit()
    db.refresh(db_url)
    return db_url

def get_db_url_by_key(db: Session, url_key: str) -> models.URL:
    return (
        db.query(models.URL)
        .filter(models.URL.key == url_key, models.URL.is_active)
        .first()
    )

def get_db_url_by_secret_key(db: Session, secret_key: str) -> models.URL:
    return (
        db.query(models.URL)
        .filter(models.URL.secret_key == secret_key,models.URL.is_active)
        .first()
    )

def update_db_clicks(db: Session, db_url: schemas.URL) -> models.URL:
    db_url.clicks += 1
    db.commit()
    db.refresh(db_url)
    return db_url

def _deactivate_url(db: Session, db_url: models.URL | None) -> models.URL | None:
    """Mark link as deleted (soft delete). Does nothing if db_url is None."""
    if db_url:
        db_url.is_active = False
        db.commit()
        db.refresh(db_url)
    return db_url

def deactivate_db_url_by_secret(db: Session, secret_key: str) -> models.URL | None:
    """Manage page + API: allowed because the caller knows the secret key."""
    db_url = get_db_url_by_secret_key(db, secret_key=secret_key)
    return _deactivate_url(db=db, db_url=db_url)

def deactivate_db_url_by_owner(db: Session, url_key: str, owner_id: int) -> models.URL | None:
    """Account page: allowed because the logged-in user owns the link."""
    db_url = (
        db.query(models.URL)
        .filter(
            models.URL.key == url_key,
            models.URL.owner_id == owner_id,
            models.URL.is_active,
        )
        .first()
    )
    return _deactivate_url(db=db, db_url=db_url)

def get_user_by_username(db: Session, username: str) -> models.User | None:
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=security.hash_password(user.password.get_secret_value()),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()

def get_urls_by_owner(db: Session, owner_id: int) -> list[models.URL]:
    return (
        db.query(models.URL)
        .filter(models.URL.owner_id == owner_id, models.URL.is_active)
        .order_by(models.URL.created_at.desc())
        .all()
    )