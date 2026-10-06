from fastapi import Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import (
    User,
)

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: DBSession = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db.execute(select(User.id).limit(1))
        if settings().job_mode == "rq":
            from redis import Redis

            Redis.from_url(settings().redis_url, socket_connect_timeout=2).ping()
    except Exception:
        raise HTTPException(503, "Database, migrations, or queue are unavailable") from None
    return {"status": "ready"}
