"""Reservation business logic (the UML sequence diagram, step by step)."""

import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import (
    Event,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Reservation,
    ReservationStatus,
    Role,
    Ticket,
    TicketStatus,
    User,
    utcnow,
)
from app.services import payment as payment_service


def _new_ticket_code() -> str:
    return secrets.token_hex(8).upper()


def _release_seats(db: Session, event_id: int, seats: int) -> None:
    db.execute(
        update(Event)
        .where(Event.id == event_id)
        .values(places_remaining=Event.places_remaining + seats)
    )


def get_reservation(
    db: Session, user: User, reservation_id: int, *, allow_admin: bool = False
) -> Reservation:
    """Return a reservation the user may access, otherwise 404.

    404 (not 403) for other people's reservations: IDs can't be probed.
    """
    reservation = db.get(Reservation, reservation_id)
    is_owner = reservation is not None and reservation.user_id == user.id
    is_admin = allow_admin and user.role == Role.ADMIN
    if reservation is None or not (is_owner or is_admin):
        raise NotFoundError("Reservation not found")
    return reservation


def list_user_reservations(
    db: Session, user: User, limit: int, offset: int
) -> list[Reservation]:
    stmt = (
        select(Reservation)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt))


def create_reservation(
    db: Session, user: User, event_id: int, seats: int
) -> Reservation:
    """Steps 3-5: check availability, hold the seats, create a pending reservation."""
    event = db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    if event.date <= utcnow():
        raise ConflictError("This event has already started")
    total_cents = event.price_cents * seats

    # Atomic "check and decrement" in a single SQL statement: two concurrent
    # requests can never sell the same last seat.
    result = db.execute(
        update(Event)
        .where(Event.id == event_id, Event.places_remaining >= seats)
        .values(places_remaining=Event.places_remaining - seats)
    )
    if result.rowcount == 0:
        db.rollback()
        raise ConflictError("Not enough seats available")

    reservation = Reservation(
        user_id=user.id,
        event_id=event_id,
        seats=seats,
        total_cents=total_cents,
        status=ReservationStatus.PENDING,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)
    return reservation


def pay_reservation(
    db: Session,
    reservation: Reservation,
    method: PaymentMethod,
    simulate_refusal: bool = False,
) -> Reservation:
    """Steps 6-9: create a payment, call the gateway, confirm or cancel the reservation."""
    if reservation.status != ReservationStatus.PENDING:
        raise ConflictError("Reservation is not pending")

    payment = Payment(
        reservation_id=reservation.id,
        method=method,
        status=PaymentStatus.ACCEPTED
        if not simulate_refusal
        else PaymentStatus.REFUSED,
        amount_cents=reservation.total_cents,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    if payment.status == PaymentStatus.ACCEPTED:
        # Create tickets and confirm the reservation.
        tickets = [
            Ticket(
                reservation_id=reservation.id,
                code=_new_ticket_code(),
                status=TicketStatus.VALID,
            )
            for _ in range(reservation.seats)
        ]
        db.add_all(tickets)
        reservation.status = ReservationStatus.CONFIRMED
    else:
        # Release the seats and cancel the reservation.
        _release_seats(db, reservation.event_id, reservation.seats)
        reservation.status = ReservationStatus.CANCELLED

    db.commit()
    db.refresh(reservation)
    return reservation