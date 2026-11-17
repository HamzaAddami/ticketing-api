"""Pydantic schemas: what goes in and out of the API.

Models are never returned directly, so fields like password_hash can't leak.
"""

from datetime import datetime, timezone

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.core.config import get_settings
from app.models import (
    PaymentMethod,
    PaymentStatus,
    ReservationStatus,
    Role,
    TicketStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth / users ----------


class UserCreate(BaseModel):
    # No "role" field: nobody can self-register as admin.
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:  # bcrypt only uses the first 72 bytes
            raise ValueError("password must be at most 72 bytes")
        return v


class UserOut(ORMModel):
    id: int
    name: str
    email: EmailStr
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- events ----------


def _must_be_future(v: datetime | None) -> datetime | None:
    if v is not None and v <= datetime.now(timezone.utc):
        raise ValueError("date must be in the future")
    return v


class EventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    date: AwareDatetime
    location: str = Field(min_length=1, max_length=200)
    price_cents: int = Field(ge=0, le=10_000_000)
    places_total: int = Field(ge=1, le=100_000)

    _check_date = field_validator("date")(_must_be_future)


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    date: AwareDatetime | None = None
    location: str | None = Field(default=None, min_length=1, max_length=200)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    places_total: int | None = Field(default=None, ge=1, le=100_000)

    _check_date = field_validator("date")(_must_be_future)


class EventOut(ORMModel):
    id: int
    title: str
    date: datetime
    location: str
    price_cents: int
    places_total: int
    places_remaining: int


# ---------- reservations / payments / tickets ----------


class ReservationCreate(BaseModel):
    event_id: int
    seats: int = Field(ge=1, le=get_settings().max_seats_per_reservation)


class PaymentRequest(BaseModel):
    method: PaymentMethod = PaymentMethod.CARD
    # Test helper: the payment provider is simulated, this forces a refusal
    simulate_refusal: bool = False


class PaymentOut(ORMModel):
    id: int
    method: PaymentMethod
    status: PaymentStatus
    amount_cents: int
    created_at: datetime


class TicketOut(ORMModel):
    id: int
    code: str
    status: TicketStatus
    created_at: datetime


class ReservationOut(ORMModel):
    id: int
    user_id: int
    event_id: int
    seats: int
    total_cents: int
    status: ReservationStatus
    created_at: datetime
    tickets: list[TicketOut]
    payment: PaymentOut | None


class AdminReservationOut(ReservationOut):
    user: UserOut
    event: EventOut