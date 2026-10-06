from fastapi import Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import (
    Organization,
    Occurrence,
    Incident,
    Investigation,
    ToolCall,
    Review,
    MonitoringCheck,
    now,
)
from app.security import current_user, scoped
from app.api.schemas import (
    ReviewIn,
    InvestigationIn,
    IncidentReanalysisIn,
)
from app.detectors import safe_text, sanitize
from app.analysis import (
    capture_scope,
    guard_incident_list,
)
from app.sources import lock_source

from fastapi import APIRouter
from app.serialization import record, page
from app.scans import submit_scan
from app.incidents import current_analysis, incident_report, investigation_record
from app.workers import jobs

router = APIRouter(prefix="/api", tags=["incidents"])


@router.post("/incidents/{incident_id}/reanalyses", status_code=202)
def reanalyze_incident(
    incident_id: str,
    payload: IncidentReanalysisIn,
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    incident = scoped(db, Incident, incident_id, user.workspace_id)
    source = lock_source(db, payload.source_id, user.workspace_id)
    document, _ = current_analysis(db, incident, payload.expected_analysis_revision, require_available=False)
    if not db.scalar(
        select(Occurrence.id).where(Occurrence.source_id == source.id, Occurrence.document_id == document.id)
    ):
        raise HTTPException(409, "Choose a source that previously supplied this document")
    return record(
        submit_scan(
            db,
            source,
            analysis_request={
                "document_id": document.id,
                "expected_revision": document.analysis_revision,
                "reason": safe_text(payload.reason),
                "requested_by": user.id,
            },
        )
    )


@router.get("/incidents")
def incidents(
    q: str = "",
    priority: str = "",
    status: str = "",
    category: str = "",
    organization: str = "",
    since: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    extra = []
    for column, value in (
        (Incident.priority, priority),
        (Incident.status, status),
        (Incident.category, category),
    ):
        if value:
            if column is Incident.status and value == "active":
                extra.append(column.in_(["open", "confirmed", "needs_context"]))
            else:
                extra.append(column == value)
    if q:
        extra.append(Incident.title.ilike(f"%{q[:200]}%"))
    if since:
        extra.append(Incident.created_at >= since)
    if organization:
        # Portable JSON search for a validated UUID, including SQLite local mode.
        scoped(db, Organization, organization, user.workspace_id)
        from sqlalchemy import cast, String

        extra.append(cast(Incident.attribution, String).contains(organization))
    return guard_incident_list(
        db, page(db, Incident, user.workspace_id, offset, limit, extra), user.workspace_id
    )


@router.get("/incidents/{incident_id}")
def incident_detail(
    incident_id: str,
    analysis_revision: int | None = Query(None, ge=1),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    return incident_report(
        db, scoped(db, Incident, incident_id, user.workspace_id), user.workspace_id, analysis_revision
    )


@router.post("/incidents/{incident_id}/reviews", status_code=201)
def review(incident_id: str, payload: ReviewIn, user=Depends(current_user), db: DBSession = Depends(get_db)):
    incident = scoped(db, Incident, incident_id, user.workspace_id)
    _, analysis = current_analysis(db, incident, payload.analysis_revision)
    review = Review(
        analysis_revision=analysis.revision,
        workspace_id=user.workspace_id,
        incident_id=incident.id,
        user_id=user.id,
        action=payload.action,
        reason=safe_text(payload.reason),
        priority=payload.priority,
    )
    db.add(review)
    statuses = {
        "confirm": "confirmed",
        "dismiss": "dismissed",
        "request_context": "needs_context",
        "remediate": "remediated",
        "reopen": "open",
    }
    if payload.action in statuses:
        incident.status = statuses[payload.action]
    if payload.priority:
        incident.priority = payload.priority
    incident.updated_at = now()
    db.commit()
    return record(review)


@router.get("/incidents/{incident_id}/export")
def export(
    incident_id: str,
    analysis_revision: int | None = Query(None, ge=1),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    report = incident_report(
        db, scoped(db, Incident, incident_id, user.workspace_id), user.workspace_id, analysis_revision
    )
    if report["analysis"]["restricted"]:
        raise HTTPException(
            409, "This revision is restricted. Reanalyze original bytes and export the new revision."
        )
    return JSONResponse(
        sanitize({"schema_version": "2", "exported_at": now(), "redacted": True, "report": report}),
        headers={
            "Content-Disposition": f'attachment; filename="leaklens-{incident_id}-r{report["analysis_revision"]}.json"'
        },
    )


@router.post("/incidents/{incident_id}/investigations", status_code=202)
def investigate(
    incident_id: str, payload: InvestigationIn, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    incident = scoped(db, Incident, incident_id, user.workspace_id)
    _, analysis = current_analysis(db, incident, payload.analysis_revision)
    if payload.mode == "live" and (settings().llm_mode != "live" or not settings().anthropic_api_key):
        raise HTTPException(
            409, "Live agent is not configured; enable it with server-side environment variables"
        )
    active = db.scalar(
        select(Investigation).where(
            Investigation.incident_id == incident.id,
            Investigation.analysis_revision == analysis.revision,
            Investigation.status.in_(["queued", "running"]),
        )
    )
    if active:
        return record(active)
    run = Investigation(
        analysis_revision=analysis.revision,
        scope_snapshot=capture_scope(db, incident, analysis),
        workspace_id=user.workspace_id,
        incident_id=incident.id,
        mode=payload.mode,
        model=settings().llm_model if payload.mode == "live" else None,
    )
    db.add(run)
    db.commit()
    from app.agent.runner import run_investigation

    try:
        jobs.enqueue(run_investigation, run.id)
    except Exception:
        run.status = "failed"
        run.error = "Worker queue unavailable"
        db.commit()
    return record(run)


@router.get("/investigations/{run_id}")
def investigation(run_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    run = scoped(db, Investigation, run_id, user.workspace_id)
    calls = db.scalars(
        select(ToolCall)
        .where(ToolCall.investigation_id == run.id, ToolCall.workspace_id == user.workspace_id)
        .order_by(ToolCall.created_at)
    ).all()
    result = investigation_record(db, run)
    return {**result, "tool_calls": [] if result["restricted"] else [record(c) for c in calls]}


@router.get("/monitoring/{occurrence_id}")
def monitoring(occurrence_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    scoped(db, Occurrence, occurrence_id, user.workspace_id)
    return page(
        db,
        MonitoringCheck,
        user.workspace_id,
        limit=100,
        extra=[MonitoringCheck.occurrence_id == occurrence_id],
    )
