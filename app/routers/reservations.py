from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.models import Reservation
from app.schemas import PaymentRequest, ReservationCreate, ReservationOut
from app.services.reservations import (
    create_reservation,
    get_reservation,
    list_user_reservations,
    pay_reservation,
)

router = APIRouter(prefix="/reservations", tags=["reservations"])


@router.post("", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
def reserve(payload: ReservationCreate, user: CurrentUser, db: DbSession) -> Reservation:
    return create_reservation(db, user, payload.event_id, payload.seats)


@router.get("/me", response_model=list[ReservationOut])
def my_reservations(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Reservation]:
    return list_user_reservations(db, user, limit, offset)


@router.get("/{reservation_id}", response_model=ReservationOut)
def reservation_details(
    reservation_id: int, user: CurrentUser, db: DbSession
) -> Reservation:
    return get_reservation(db, user, reservation_id)


@router.post("/{reservation_id}/pay", response_model=ReservationOut)
def pay(
    reservation_id: int,
    payload: PaymentRequest,
    user: CurrentUser,
    db: DbSession,
) -> Reservation:
    reservation = get_reservation(db, user, reservation_id)
    return pay_reservation(
        db,
        reservation,
        payload.method,
        simulate_refusal=payload.simulate_refusal,
    )
