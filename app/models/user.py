"""User account model with bcrypt-hashed passwords."""

from __future__ import annotations

import bcrypt
from flask_login import UserMixin
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(UserMixin, TimestampMixin, Base):
    """A person who can log in and own finance records.

    Passwords are stored as bcrypt hashes. The plaintext password is never
    written to the database or to logs.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active_flag: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def set_password(self, plaintext: str) -> None:
        if not plaintext or len(plaintext) < 8:
            raise ValueError("Password must be at least 8 characters.")
        self.password_hash = bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

    def check_password(self, plaintext: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.checkpw(plaintext.encode("utf-8"), self.password_hash.encode("utf-8"))

    @property
    def is_active(self) -> bool:  # type: ignore[override]
        return self.is_active_flag

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
