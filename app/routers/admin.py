from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.deps import AdminUser, DbSession
from app.models import Reservation
from app.schemas import AdminReservationOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/reservations", response_model=list[AdminReservationOut])
def list_all_reservations(
    _admin: AdminUser,
    db: DbSession,
    event_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """UML "Consulter les reservations" (sales and remaining seats)."""
    stmt = select(Reservation).order_by(Reservation.id.desc()).limit(limit).offset(offset)
    if event_id is not None:
        stmt = stmt.where(Reservation.event_id == event_id)
    return list(db.scalars(stmt))