"""Source lifecycle and scan provenance shared by API operations."""

from copy import deepcopy
from fastapi import HTTPException
from sqlalchemy import select, update
from app.models import Source, SourceEvent, ScanJob


def snapshot(source):
    return deepcopy(
        {
            "name": source.name,
            "kind": source.kind,
            "config": source.config,
            "access_context": source.access_context,
            "revision": source.revision,
            "archived_at": source.archived_at,
        }
    )


def record_event(db, source, action, user_id):
    db.add(
        SourceEvent(
            workspace_id=source.workspace_id,
            source_id=source.id,
            user_id=user_id,
            action=action,
            revision=source.revision,
            snapshot=snapshot(source),
        )
    )


def lock_source(db, source_id, workspace_id):
    # A no-op write serializes source mutation/scan submission on SQLite as well
    # as PostgreSQL. The caller commits the lifecycle event/job in this transaction.
    result = db.execute(
        update(Source)
        .where(Source.id == source_id, Source.workspace_id == workspace_id)
        .values(revision=Source.revision)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(404, "Record not found")
    return db.scalar(select(Source).where(Source.id == source_id).execution_options(populate_existing=True))


def require_current(source, expected_revision):
    if source.revision != expected_revision:
        raise HTTPException(409, "Source changed since you opened it. Refresh and try again.")


def require_active(source):
    if source.archived_at:
        raise HTTPException(409, "Restore this archived source before checking or scanning it")


def require_idle(db, source):
    if db.scalar(
        select(ScanJob.id)
        .where(ScanJob.source_id == source.id, ScanJob.status.in_(["queued", "running"]))
        .limit(1)
    ):
        raise HTTPException(
            409, "Wait for the active scan to finish, or cancel it before changing this source"
        )
