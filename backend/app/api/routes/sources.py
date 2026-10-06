from typing import Literal
from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import (
    Source,
    SourceEvent,
    now,
)
from app.security import current_user, scoped
from app.api.schemas import (
    SourceIn,
    SourceUpdate,
    SourceArchiveIn,
)
from app.connectors.policy import validate_url, local_repository
from app.detectors import safe_text
from app.sources import record_event, lock_source, require_current, require_active, require_idle

from fastapi import APIRouter
from app.serialization import record, page

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources")
def sources(
    q: str = Query("", max_length=200),
    state: Literal["active", "archived", "all"] = "active",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    filters = []
    if q.strip():
        filters.append(Source.name.icontains(q.strip(), autoescape=True))
    if state != "all":
        filters.append(Source.archived_at.is_(None) if state == "active" else Source.archived_at.is_not(None))
    return page(db, Source, user.workspace_id, offset, limit, filters)


@router.post("/sources", status_code=201)
def create_source(payload: SourceIn, user=Depends(current_user), db: DBSession = Depends(get_db)):
    config = payload.config.model_dump(exclude_none=True)
    if config.get("url"):
        validate_url(config["url"], config)
    else:
        local_repository(config["path"])
    source = Source(
        workspace_id=user.workspace_id,
        name=safe_text(payload.name),
        kind=payload.kind,
        config=config,
        access_context=payload.access_context,
    )
    db.add(source)
    db.flush()
    record_event(db, source, "created", user.id)
    db.commit()
    return record(source)


@router.put("/sources/{source_id}")
def update_source(
    source_id: str, payload: SourceUpdate, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    source = scoped(db, Source, source_id, user.workspace_id)
    config = payload.config.model_dump(exclude_none=True)
    if source.kind == "upload":
        raise HTTPException(409, "Uploads are fixed snapshots; upload a new file to change the input")
    if payload.kind != source.kind or any(config.get(k) != source.config.get(k) for k in ("url", "path")):
        raise HTTPException(409, "Connect a new source to change its type or destination")
    # Validate before holding the database write lock during DNS resolution.
    if config.get("url"):
        validate_url(config["url"], config)
    else:
        local_repository(config["path"])
    source = lock_source(db, source_id, user.workspace_id)
    require_current(source, payload.expected_revision)
    require_active(source)
    require_idle(db, source)
    source.name = safe_text(payload.name)
    source.config = config
    source.access_context = payload.access_context
    source.revision += 1
    source.health = "unchecked"
    source.last_checked = None
    source.checkpoint = {}
    record_event(db, source, "updated", user.id)
    db.commit()
    return record(source)


@router.post("/sources/{source_id}/archive")
def archive_source(
    source_id: str, payload: SourceArchiveIn, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    source = lock_source(db, source_id, user.workspace_id)
    require_current(source, payload.expected_revision)
    if bool(source.archived_at) != payload.archived:
        require_idle(db, source)
        source.archived_at = now() if payload.archived else None
        source.revision += 1
        record_event(db, source, "archived" if payload.archived else "restored", user.id)
    db.commit()
    return record(source)


@router.get("/sources/{source_id}/history")
def source_history(
    source_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    scoped(db, Source, source_id, user.workspace_id)
    return page(db, SourceEvent, user.workspace_id, offset, limit, [SourceEvent.source_id == source_id])


@router.post("/sources/{source_id}/check")
def check_source(source_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    source = scoped(db, Source, source_id, user.workspace_id)
    require_active(source)
    try:
        if source.kind == "upload":
            exists = (settings().data_dir.resolve() / "uploads" / source.id).is_file()
            if not exists:
                raise ValueError("Raw upload expired; preserved redacted evidence remains available")
        elif source.config.get("path"):
            from app.connectors.git import run

            run(local_repository(source.config["path"]), ["rev-parse", "--verify", "HEAD"])
        else:
            from app.connectors.http import fetch

            url = source.config["url"]
            if source.kind == "git":
                validate_url(url, source.config)
                source.health = "destination_validated"
                source.last_checked = now()
                db.commit()
                return {
                    "status": source.health,
                    "detail": "Destination validated; repository access is checked by the scan",
                }
            status, _, _, _ = fetch(url, source.config)
            if status != 200:
                raise ValueError(f"Source returned HTTP {status}")
        source.health = "reachable"
        detail = "Source connection succeeded"
    except ValueError as exc:
        source.health = "error"
        detail = safe_text(str(exc))
    except Exception:
        source.health = "error"
        detail = "Connection failed or timed out"
    source.last_checked = now()
    db.commit()
    return {"status": source.health, "detail": detail}
