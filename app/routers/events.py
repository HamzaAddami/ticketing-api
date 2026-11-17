from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.core.errors import ConflictError, NotFoundError
from app.deps import AdminUser, DbSession
from app.models import Event, Reservation
from app.schemas import EventCreate, EventOut, EventUpdate

router = APIRouter(prefix="/events", tags=["events"])


def _get_event(db: DbSession, event_id: int) -> Event:
    event = db.get(Event, event_id)
    if event is None:
        raise NotFoundError("Event not found")
    return event


# ---- public (visitor): UML "Consulter les evenements" ----


@router.get("", response_model=list[EventOut])
def list_events(
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Event).order_by(Event.date, Event.id).limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: DbSession):
    return _get_event(db, event_id)


# ---- admin: UML "Gerer les evenements" ----


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(payload: EventCreate, _admin: AdminUser, db: DbSession):
    event = Event(**payload.model_dump(), places_remaining=payload.places_total)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{event_id}", response_model=EventOut)
def update_event(event_id: int, payload: EventUpdate, _admin: AdminUser, db: DbSession):
    event = _get_event(db, event_id)
    changes = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}

    if "places_total" in changes:
        # Keep the number of already-held seats unchanged.
        new_remaining = event.places_remaining + (changes["places_total"] - event.places_total)
        if new_remaining < 0:
            raise ConflictError("places_total is lower than the seats already reserved")
        event.places_remaining = new_remaining

    for field, value in changes.items():
        setattr(event, field, value)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: int, _admin: AdminUser, db: DbSession):
    event = _get_event(db, event_id)
    has_reservations = db.scalar(
        select(Reservation.id).where(Reservation.event_id == event_id).limit(1)
    )
    if has_reservations is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Event has reservations")
    db.delete(event)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)