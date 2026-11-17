"""Create tables and optional initial data at startup.

For a real project, replace create_all() with Alembic migrations.
"""

from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Event, Role, User, utcnow


def init_db() -> None:
    settings = get_settings()
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        if settings.admin_email and settings.admin_password:
            email = settings.admin_email.lower()
            if db.scalar(select(User.id).where(User.email == email)) is None:
                db.add(
                    User(
                        name="Administrator",
                        email=email,
                        password_hash=hash_password(settings.admin_password),
                        role=Role.ADMIN,
                    )
                )

        if settings.seed_demo_data and db.scalar(select(Event.id).limit(1)) is None:
            now = utcnow()
            db.add_all(
                [
                    Event(title="Jazz Night", date=now + timedelta(days=14),
                          location="Casablanca", price_cents=15000,
                          places_total=100, places_remaining=100),
                    Event(title="Tech Conference", date=now + timedelta(days=30),
                          location="Rabat", price_cents=30000,
                          places_total=250, places_remaining=250),
                    Event(title="Football Match", date=now + timedelta(days=45),
                          location="Marrakech", price_cents=8000,
                          places_total=500, places_remaining=500),
                ]
            )
        db.commit()