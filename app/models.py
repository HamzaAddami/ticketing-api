"""SQLAlchemy models, derived from the UML class diagram.

UML name   -> class here
Utilisateur -> User        Evenement -> Event      Reservation -> Reservation
Billet      -> Ticket      Paiement  -> Payment

Money is stored as integer cents (no float rounding errors).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.types import UTCDateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(enum.StrEnum):
    CLIENT = "client"
    ADMIN = "admin"


class ReservationStatus(enum.StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class TicketStatus(enum.StrEnum):
    VALID = "valid"
    USED = "used"
    CANCELLED = "cancelled"


class PaymentMethod(enum.StrEnum):
    CARD = "card"
    PAYPAL = "paypal"


class PaymentStatus(enum.StrEnum):
    ACCEPTED = "accepted"
    REFUSED = "refused"
    REFUNDED = "refunded"


def _enum(enum_cls: type[enum.StrEnum]) -> SAEnum:
    """Store enums as plain strings (portable, readable in the DB)."""
    return SAEnum(
        enum_cls,
        native_enum=False,
        length=20,
        create_constraint=False,
        values_callable=lambda e: [member.value for member in e],
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.CLIENT)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    reservations: Mapped[list[Reservation]] = relationship(back_populates="user")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_event_price"),
        CheckConstraint(
            "places_remaining >= 0 AND places_remaining <= places_total",
            name="ck_event_places",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    date: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    location: Mapped[str] = mapped_column(String(200))
    price_cents: Mapped[int]
    places_total: Mapped[int]
    places_remaining: Mapped[int]

    reservations: Mapped[list[Reservation]] = relationship(back_populates="event")


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("seats > 0", name="ck_reservation_seats"),
        CheckConstraint("total_cents >= 0", name="ck_reservation_total"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    seats: Mapped[int]
    total_cents: Mapped[int]
    status: Mapped[ReservationStatus] = mapped_column(
        _enum(ReservationStatus), default=ReservationStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="reservations")
    event: Mapped[Event] = relationship(back_populates="reservations")
    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="reservation", cascade="all, delete-orphan"
    )
    payment: Mapped[Payment | None] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"), unique=True, index=True
    )
    method: Mapped[PaymentMethod] = mapped_column(_enum(PaymentMethod))
    status: Mapped[PaymentStatus] = mapped_column(_enum(PaymentStatus))
    amount_cents: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    reservation: Mapped[Reservation] = relationship(back_populates="payment")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("reservations.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[TicketStatus] = mapped_column(
        _enum(TicketStatus), default=TicketStatus.VALID
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    reservation: Mapped[Reservation] = relationship(back_populates="tickets")
