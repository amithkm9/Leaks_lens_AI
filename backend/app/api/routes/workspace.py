from app.api.schemas import (
    OrganizationIn,
)
from app.config import settings
from app.db import get_db
from app.detectors import availability
from app.models import (
    Document,
    EvaluationRun,
    Incident,
    Organization,
    RemediationTask,
    ScanJob,
    Source,
)
from app.remediation import ACTIVE, task_page, today
from app.security import current_user, scoped
from app.serialization import page, record
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

router = APIRouter(prefix="/api", tags=["workspace"])


@router.get("/organizations")
def organizations(user=Depends(current_user), db: DBSession = Depends(get_db)):
    return page(db, Organization, user.workspace_id, limit=100)


@router.post("/organizations", status_code=201)
def create_organization(payload: OrganizationIn, user=Depends(current_user), db: DBSession = Depends(get_db)):
    org = Organization(workspace_id=user.workspace_id, **payload.model_dump())
    db.add(org)
    db.commit()
    return record(org)


@router.put("/organizations/{organization_id}")
def update_organization(
    organization_id: str, payload: OrganizationIn, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    org = scoped(db, Organization, organization_id, user.workspace_id)
    for key, value in payload.model_dump().items():
        setattr(org, key, value)
    db.commit()
    return record(org)


@router.get("/overview")
def overview(user=Depends(current_user), db: DBSession = Depends(get_db)):
    w = user.workspace_id

    def count(model, *filters):
        return db.scalar(select(func.count()).select_from(model).where(model.workspace_id == w, *filters))

    trend = db.execute(
        select(func.substr(Incident.created_at, 1, 10), func.count())
        .where(Incident.workspace_id == w)
        .group_by(func.substr(Incident.created_at, 1, 10))
        .order_by(func.substr(Incident.created_at, 1, 10).desc())
        .limit(14)
    ).all()
    return {
        "open_incidents": count(Incident, Incident.status.in_(["open", "confirmed", "needs_context"])),
        "high_priority": count(
            Incident, Incident.priority == "high", Incident.status.in_(["open", "confirmed", "needs_context"])
        ),
        "documents": count(Document),
        "sources": count(Source, Source.archived_at.is_(None)),
        "source_issues": count(
            Source, Source.archived_at.is_(None), Source.health.in_(["error", "partial", "failed"])
        ),
        "remediation": {
            "active": count(RemediationTask, RemediationTask.status.in_(ACTIVE)),
            "overdue": count(
                RemediationTask, RemediationTask.status.in_(ACTIVE), RemediationTask.due_date < today()
            ),
            "awaiting_verification": count(
                RemediationTask, RemediationTask.status == "completed", RemediationTask.verified_at.is_(None)
            ),
            "next_tasks": task_page(db, w, limit=5, extra=[RemediationTask.status.in_(ACTIVE)])["items"],
            "due_date_timezone": "UTC",
        },
        "recent_scans": page(db, ScanJob, w, limit=5)["items"],
        "trend": [{"date": date, "incidents": n} for date, n in reversed(trend)],
        "mode": "Live agent available"
        if settings().llm_mode == "live" and settings().anthropic_api_key
        else "LLM disabled",
    }


@router.get("/settings")
def configuration(user=Depends(current_user)):
    cfg = settings()
    return {
        "mode": cfg.llm_mode,
        "live_available": cfg.llm_mode == "live" and bool(cfg.anthropic_api_key),
        "model": cfg.llm_model if cfg.llm_mode == "live" else None,
        "detectors": availability(),
        "limits": {
            "max_file_mb": cfg.max_file_bytes // 1024 // 1024,
            "max_file_bytes": cfg.max_file_bytes,
            "documents_per_scan": cfg.max_documents,
            "pdf_pages": cfg.max_pdf_pages,
            "csv_rows": cfg.max_csv_rows,
            "raw_retention_hours": cfg.raw_retention_hours,
            "agent_max_tools": cfg.agent_max_tools,
        },
        "read_only": cfg.public_read_only,
    }


@router.get("/evaluations")
def evaluations(user=Depends(current_user), db: DBSession = Depends(get_db)):
    return page(db, EvaluationRun, user.workspace_id)
