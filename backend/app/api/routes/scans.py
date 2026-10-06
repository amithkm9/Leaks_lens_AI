from pathlib import Path
from fastapi import Depends, HTTPException, Request, UploadFile, File, Query
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import (
    Source,
    ScanJob,
    Document,
    now,
)
from app.security import current_user, scoped
from app.api.schemas import (
    SourceReanalysisIn,
)
from app.detectors import safe_text
from app.parsers import supported
from app.sources import record_event, lock_source, require_current

from fastapi import APIRouter
from app.serialization import record, page
from app.scans import submit_scan

router = APIRouter(prefix="/api", tags=["scans"])


@router.post("/sources/{source_id}/scans", status_code=202)
def start_scan(source_id: str, request: Request, user=Depends(current_user), db: DBSession = Depends(get_db)):
    source = scoped(db, Source, source_id, user.workspace_id)
    key = request.headers.get("idempotency-key")
    if key and len(key) > 100:
        raise HTTPException(400, "Idempotency key is too long")
    return record(submit_scan(db, source, key))


@router.post("/uploads", status_code=202)
async def upload(file: UploadFile = File(...), user=Depends(current_user), db: DBSession = Depends(get_db)):
    name = Path((file.filename or "upload.txt").replace("\\", "/")).name[:250]
    if not supported(name):
        raise HTTPException(415, "Unsupported file format")
    source = Source(
        workspace_id=user.workspace_id,
        name=safe_text(name),
        kind="upload",
        config={"filename": safe_text(name)},
        access_context="supplied",
    )
    db.add(source)
    db.flush()
    root = settings().data_dir.resolve() / "uploads"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / source.id
    total = 0
    try:
        with path.open("xb") as output:
            path.chmod(0o600)
            while chunk := await file.read(64 * 1024):
                total += len(chunk)
                if total > settings().max_file_bytes:
                    raise HTTPException(413, "File exceeds the configured upload limit")
                output.write(chunk)
        if not total:
            raise HTTPException(400, "File is empty")
        record_event(db, source, "created", user.id)
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        db.rollback()
        raise
    finally:
        await file.close()
    return record(submit_scan(db, source))


@router.get("/scans")
def scans(
    source_id: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    if source_id:
        scoped(db, Source, source_id, user.workspace_id)
    return page(
        db, ScanJob, user.workspace_id, offset, limit, [ScanJob.source_id == source_id] if source_id else []
    )


@router.get("/scans/{job_id}")
def scan(job_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return record(scoped(db, ScanJob, job_id, user.workspace_id))


@router.post("/scans/{job_id}/cancel")
def cancel_scan(job_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    job = scoped(db, ScanJob, job_id, user.workspace_id)
    if job.status in {"queued", "running"}:
        job.cancel_requested = True
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = now()
        db.commit()
    return record(job)


@router.post("/scans/{job_id}/retry", status_code=202)
def retry_scan(job_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    job = scoped(db, ScanJob, job_id, user.workspace_id)
    if job.status in {"queued", "running"}:
        raise HTTPException(409, "The job is still active")
    source = scoped(db, Source, job.source_id, user.workspace_id)
    if job.analysis_request:
        require_current(source, job.source_snapshot["revision"])
        target = job.analysis_request.get("document_id")
        if (
            target
            and scoped(db, Document, target, user.workspace_id).analysis_revision
            != job.analysis_request["expected_revision"]
        ):
            raise HTTPException(
                409,
                "The document already has a newer analysis. Open the incident to request another revision.",
            )
    return record(submit_scan(db, source, analysis_request=job.analysis_request))


@router.post("/sources/{source_id}/reanalyses", status_code=202)
def reanalyze_source(
    source_id: str, payload: SourceReanalysisIn, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    source = lock_source(db, source_id, user.workspace_id)
    require_current(source, payload.expected_revision)
    return record(
        submit_scan(
            db, source, analysis_request={"reason": safe_text(payload.reason), "requested_by": user.id}
        )
    )
