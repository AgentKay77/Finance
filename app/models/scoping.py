"""Per-user data isolation enforcement.

Every owned table inherits :class:`UserOwnedMixin`, which gives it a
``user_id`` foreign key to ``users.id``. Routes use
:func:`current_user_query` to start any query against an owned model so
the ``user_id`` filter is applied automatically. Forgetting to filter is
the kind of mistake that leaks data between household accounts; routing
queries through this helper makes the intent explicit and grep-able.

We deliberately do not use SQLAlchemy global event listeners to inject
``user_id`` filters — those are easy to bypass and hard to audit. A
helper that reads from ``flask_login.current_user`` and refuses to run
without an authenticated session is more honest about what's happening.
"""

from __future__ import annotations

from typing import TypeVar

from flask_login import current_user
from sqlalchemy import ForeignKey, Select, select
from sqlalchemy.orm import Mapped, mapped_column

T = TypeVar("T")


class UserOwnedMixin:
    """Adds ``user_id`` FK + index to a model."""

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )


def current_user_id() -> int:
    """Return the active user id or raise. Use inside login_required views."""

    if not getattr(current_user, "is_authenticated", False):
        raise PermissionError("No authenticated user in current request.")
    return int(current_user.id)


def current_user_query(model: type[T]) -> Select[tuple[T]]:
    """Build a SELECT pre-filtered to the current user's rows."""

    return select(model).where(model.user_id == current_user_id())
