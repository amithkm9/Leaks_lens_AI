"""Submit source work with a captured configuration and queue failure reporting."""

from fastapi import HTTPException
from sqlalchemy import select

from app.config import settings
from app.models import (
    ScanJob,
)
from app.sources import lock_source, require_active, snapshot
from app.workers import jobs


def submit_scan(db, source, key=None, analysis_request=None):
    source = lock_source(db, source.id, source.workspace_id)
    require_active(source)
    if key:
        old = db.scalar(
            select(ScanJob).where(ScanJob.workspace_id == source.workspace_id, ScanJob.idempotency_key == key)
        )
        if old:
            if old.source_id != source.id:
                raise HTTPException(409, "Idempotency key is already associated with another source")
            return old
    active = db.scalar(
        select(ScanJob).where(ScanJob.source_id == source.id, ScanJob.status.in_(["queued", "running"]))
    )
    if active:
        if analysis_request:
            raise HTTPException(409, "Wait for the active scan to finish before requesting reanalysis")
        return active
    if (
        analysis_request
        and source.kind == "upload"
        and not (settings().data_dir.resolve() / "uploads" / source.id).is_file()
    ):
        raise HTTPException(409, "Raw upload has expired; upload the original file again to reanalyze it")
    job = ScanJob(
        workspace_id=source.workspace_id,
        source_id=source.id,
        idempotency_key=key,
        source_snapshot=snapshot(source),
        analysis_request=analysis_request or {},
    )
    db.add(job)
    db.commit()
    try:
        jobs.enqueue(jobs.run_scan, job.id)
    except Exception:
        job.status = "failed"
        job.errors = ["Worker queue unavailable; retry after restoring the queue"]
        db.commit()
    return job
