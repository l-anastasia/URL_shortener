from datetime import datetime

from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

class URL(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(unique=True, index=True)
    secret_key: Mapped[str] = mapped_column(unique=True, index=True)
    target_url: Mapped[str] = mapped_column(index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    clicks: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
        )
    owner: Mapped["User | None"] = relationship()

    def __repr__(self):
        return f"<URL key={self.key!r} target_url={self.target_url!r}>"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    username: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    email: Mapped[str | None] = mapped_column(unique=True, index=True)
    