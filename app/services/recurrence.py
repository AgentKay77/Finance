"""Bill / subscription recurrence engine (Phase 4 + 6)."""

from __future__ import annotations

from datetime import date, timedelta

from app.services.amortization import _add_months


def next_occurrences(start: date, recurrence: str, horizon_end: date) -> list[date]:
    """Return all occurrence dates (inclusive of ``start``) up to ``horizon_end``.

    Recognised values: ``monthly``, ``biweekly``, ``weekly``, ``annual``,
    ``quarterly``, ``one_time``.
    """

    if start > horizon_end:
        return []
    if recurrence == "one_time":
        return [start]
    out: list[date] = []
    cursor = start
    for _ in range(2000):
        if cursor > horizon_end:
            break
        out.append(cursor)
        if recurrence == "monthly":
            cursor = _add_months(cursor, 1)
        elif recurrence == "biweekly":
            cursor = cursor + timedelta(days=14)
        elif recurrence == "weekly":
            cursor = cursor + timedelta(days=7)
        elif recurrence == "annual":
            cursor = _add_months(cursor, 12)
        elif recurrence == "quarterly":
            cursor = _add_months(cursor, 3)
        else:
            raise ValueError(f"Unknown recurrence: {recurrence!r}")
    return out


def advance_due_date(current_due: date, recurrence: str) -> date:
    """Return the next due date after ``current_due`` for the given recurrence.

    Used when a bill is marked paid so the row's ``next_due_date`` rolls
    forward.
    """

    if recurrence == "one_time":
        return current_due
    if recurrence == "monthly":
        return _add_months(current_due, 1)
    if recurrence == "biweekly":
        return current_due + timedelta(days=14)
    if recurrence == "weekly":
        return current_due + timedelta(days=7)
    if recurrence == "annual":
        return _add_months(current_due, 12)
    if recurrence == "quarterly":
        return _add_months(current_due, 3)
    raise ValueError(f"Unknown recurrence: {recurrence!r}")


__all__ = ["advance_due_date", "next_occurrences"]
