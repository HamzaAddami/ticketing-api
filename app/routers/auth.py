import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.deps import CurrentUser, DbSession
from app.models import Role, User
from app.schemas import Token, UserCreate, UserOut

logger = logging.getLogger("app.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: DbSession):
    """UML "Creer un compte". The role is always 'client'."""
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=Role.CLIENT,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # the UNIQUE constraint is the race-free check
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """UML "S'authentifier". Form fields: username (the email) and password."""
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))

    # Always run one bcrypt check, even for unknown emails (timing side channel).
    password_ok = verify_password(
        form.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if user is None or not password_ok:
        logger.warning("Failed login attempt")  # never log the password
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user