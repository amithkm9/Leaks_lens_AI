from app.config import settings
from app.db import get_db
from app.models import (
    Document,
    DocumentAnalysis,
    ScanJob,
    User,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready(db: DBSession = Depends(get_db)):
    try:
        # A reachable database with only the old users table is not ready for
        # the current API. Probe the columns required by the analysis workflow.
        db.execute(select(User.id).limit(0))
        db.execute(select(Document.analysis_revision).limit(0))
        db.execute(select(DocumentAnalysis).limit(0))
        db.execute(select(ScanJob.analysis_request).limit(0))
        if settings().job_mode == "rq":
            from redis import Redis

            Redis.from_url(settings().redis_url, socket_connect_timeout=2).ping()
    except Exception:
        raise HTTPException(503, "Database, migrations, or queue are unavailable") from None
    return {"status": "ready"}
