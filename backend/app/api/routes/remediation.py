from typing import Literal

from app.api.schemas import RemediationCreate, RemediationUpdate
from app.db import get_db
from app.incidents import current_analysis
from app.models import Incident, RemediationEvent, RemediationTask, User
from app.remediation import create_task, task_filters, task_page, task_record, update_task
from app.security import current_user, scoped
from app.serialization import page
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

router = APIRouter(prefix="/api", tags=["remediation"])


@router.get("/workspace/members")
def members(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    query = select(User.id, User.email).where(User.workspace_id == user.workspace_id)
    return {
        "items": [
            dict(row) for row in db.execute(query.order_by(User.email).offset(offset).limit(limit)).mappings()
        ],
        "total": db.scalar(select(func.count()).select_from(query.subquery())),
        "offset": offset,
        "limit": limit,
    }


@router.get("/remediation-tasks")
def tasks(
    state: Literal[
        "active",
        "all",
        "overdue",
        "awaiting_verification",
        "open",
        "in_progress",
        "blocked",
        "completed",
        "cancelled",
    ] = "active",
    owner: Literal["all", "me", "unassigned"] = "all",
    incident_id: str = "",
    analysis_revision: int | None = Query(None, ge=1),
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    filters = task_filters(state, owner, user)
    if incident_id:
        scoped(db, Incident, incident_id, user.workspace_id)
        filters.append(RemediationTask.incident_id == incident_id)
    if analysis_revision is not None:
        filters.append(RemediationTask.analysis_revision == analysis_revision)
    return task_page(db, user.workspace_id, offset, limit, filters)


@router.post("/incidents/{incident_id}/remediation-tasks", status_code=201)
def create(
    incident_id: str, payload: RemediationCreate, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    incident = scoped(db, Incident, incident_id, user.workspace_id)
    current_analysis(db, incident, payload.analysis_revision)
    return create_task(db, incident, payload, user)


@router.put("/remediation-tasks/{task_id}")
def update(
    task_id: str, payload: RemediationUpdate, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    return update_task(db, task_id, payload, user)


@router.get("/remediation-tasks/{task_id}/history")
def history(
    task_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    task = scoped(db, RemediationTask, task_id, user.workspace_id)
    blocked = task_record(db, task)["analysis_restricted"]
    result = page(
        db, RemediationEvent, user.workspace_id, offset, limit, [RemediationEvent.task_id == task.id]
    )
    actors = dict(
        db.execute(
            select(User.id, User.email).where(
                User.workspace_id == user.workspace_id,
                User.id.in_([item["user_id"] for item in result["items"]]),
            )
        ).all()
    )
    for item in result["items"]:
        item["actor_email"] = actors.get(item["user_id"])
        if blocked:
            item.update(reason="Historical task text restricted", snapshot={})
    return result
