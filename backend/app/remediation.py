"""Audited work tied to evidence; task completion never changes incident disposition."""

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.analysis import get_analysis, redaction_manifest, restricted
from app.detectors import safe_text
from app.models import (
    Document,
    DocumentAnalysis,
    Evidence,
    Incident,
    RemediationEvent,
    RemediationTask,
    User,
    now,
)
from app.security import scoped
from app.serialization import record

ACTIVE = ("open", "in_progress", "blocked")
RESTRICTED_TEXT = "Task text restricted; reanalyze original bytes before creating new follow-up work."


def today():
    return datetime.now(timezone.utc).date().isoformat()


def task_filters(state, owner, user):
    filters = []
    if state in {"active", "overdue"}:
        filters.append(RemediationTask.status.in_(ACTIVE))
        if state == "overdue":
            filters.append(RemediationTask.due_date < today())
    elif state == "awaiting_verification":
        filters.extend([RemediationTask.status == "completed", RemediationTask.verified_at.is_(None)])
    elif state != "all":
        filters.append(RemediationTask.status == state)
    if owner == "me":
        filters.append(RemediationTask.owner_id == user.id)
    elif owner == "unassigned":
        filters.append(RemediationTask.owner_id.is_(None))
    return filters


def task_page(db, workspace, offset=0, limit=25, extra=()):
    base = select(RemediationTask).where(RemediationTask.workspace_id == workspace, *extra)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.execute(
        select(RemediationTask, Incident, Document, DocumentAnalysis, User)
        .join(Incident, (Incident.id == RemediationTask.incident_id) & (Incident.workspace_id == workspace))
        .join(Document, (Document.id == Incident.document_id) & (Document.workspace_id == workspace))
        .outerjoin(
            DocumentAnalysis,
            (DocumentAnalysis.document_id == Document.id)
            & (DocumentAnalysis.workspace_id == workspace)
            & (DocumentAnalysis.revision == RemediationTask.analysis_revision),
        )
        .outerjoin(User, (User.id == RemediationTask.owner_id) & (User.workspace_id == workspace))
        .where(RemediationTask.workspace_id == workspace, *extra)
        .order_by(
            RemediationTask.due_date.is_(None),
            RemediationTask.due_date,
            RemediationTask.created_at,
            RemediationTask.id,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    manifest = redaction_manifest()
    date = today()
    items = []
    for task, incident, document, analysis, owner in rows:
        blocked = restricted(analysis, manifest)
        item = {
            **record(task),
            "owner_email": owner.email if owner else None,
            "incident_title": incident.title,
            "current_analysis_revision": document.analysis_revision,
            "analysis_restricted": blocked,
            "overdue": task.status in ACTIVE and task.due_date is not None and task.due_date < date,
        }
        if blocked:
            item.update(title=RESTRICTED_TEXT, action_taken="", verification_notes="", evidence_ids=[])
        items.append(item)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def task_record(db, task):
    return task_page(db, task.workspace_id, limit=1, extra=[RemediationTask.id == task.id])["items"][0]


def validate_references(db, payload, incident):
    if payload.owner_id:
        scoped(db, User, payload.owner_id, incident.workspace_id)
    evidence_ids = set(payload.evidence_ids)
    if len(evidence_ids) != len(payload.evidence_ids):
        raise HTTPException(422, "Choose each evidence reference only once")
    if evidence_ids:
        valid = set(
            db.scalars(
                select(Evidence.id).where(
                    Evidence.id.in_(evidence_ids),
                    Evidence.workspace_id == incident.workspace_id,
                    Evidence.document_id == incident.document_id,
                    Evidence.analysis_revision == payload.analysis_revision,
                )
            )
        )
        if valid != evidence_ids:
            raise HTTPException(422, "Evidence must belong to this incident and analysis revision")


def event(db, task, user, reason):
    db.flush()
    owner = db.get(User, task.owner_id) if task.owner_id else None
    db.add(
        RemediationEvent(
            workspace_id=task.workspace_id,
            task_id=task.id,
            user_id=user.id,
            revision=task.revision,
            reason=safe_text(reason),
            snapshot={**record(task), "owner_email": owner.email if owner else None},
        )
    )


def create_task(db, incident, payload, user):
    validate_references(db, payload, incident)
    task = RemediationTask(
        workspace_id=user.workspace_id,
        incident_id=incident.id,
        **payload.model_dump(mode="json", exclude={"title"}),
        title=safe_text(payload.title),
    )
    db.add(task)
    event(db, task, user, "Task created")
    db.commit()
    return task_record(db, task)


def update_task(db, task_id, payload, user):
    # Serialize updates on SQLite and PostgreSQL, then compare the version read by the user.
    result = db.execute(
        update(RemediationTask)
        .where(RemediationTask.id == task_id, RemediationTask.workspace_id == user.workspace_id)
        .values(revision=RemediationTask.revision)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise HTTPException(404, "Record not found")
    task = scoped(db, RemediationTask, task_id, user.workspace_id)
    db.refresh(task)
    if task.revision != payload.expected_revision:
        raise HTTPException(409, "Task changed since you opened it. Refresh and try again.")
    if task.analysis_revision != payload.analysis_revision:
        raise HTTPException(409, "A task must keep its original analysis revision")
    incident = scoped(db, Incident, task.incident_id, user.workspace_id)
    document = scoped(db, Document, incident.document_id, user.workspace_id)
    if restricted(get_analysis(db, document, task.analysis_revision)):
        raise HTTPException(409, "Task evidence is restricted; reanalyze original bytes and create new work")
    validate_references(db, payload, incident)
    previous = (task.action_taken, task.verification_method, task.verification_notes, task.evidence_ids)
    for key, value in payload.model_dump(mode="json", exclude={"expected_revision", "reason"}).items():
        setattr(
            task, key, safe_text(value) if key in {"title", "action_taken", "verification_notes"} else value
        )
    timestamp = now()
    if not task.verification_method:
        task.verified_at = task.verified_by = None
    elif not task.verified_at or previous != (
        task.action_taken,
        task.verification_method,
        task.verification_notes,
        task.evidence_ids,
    ):
        task.verified_at, task.verified_by = timestamp, user.id
    task.updated_at = timestamp
    task.revision += 1
    event(db, task, user, payload.reason)
    db.commit()
    return task_record(db, task)
