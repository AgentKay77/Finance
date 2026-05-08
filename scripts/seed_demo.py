"""Seed a demo user. Loan/asset seeding lands in Phase 2+.

Usage (from project root):
    python -m scripts.seed_demo
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app import create_app
from app.extensions import db
from app.models import User

DEMO_EMAIL = "demo@finance.local"
DEMO_PASSWORD = "demo-password-123"


def main() -> int:
    app = create_app()
    with app.app_context():
        existing = db.session.execute(
            select(User).where(User.email == DEMO_EMAIL)
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Demo user already exists: {DEMO_EMAIL}")
            return 0
        user = User(email=DEMO_EMAIL, display_name="Demo")
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.commit()
        print(f"Created demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
