from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession) -> dict[str, str]:
    """Liveness + DB check, no authentication. Use it for Docker HEALTHCHECK."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok"}