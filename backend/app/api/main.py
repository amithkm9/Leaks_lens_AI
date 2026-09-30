import logging
import time
from collections import OrderedDict, deque
from threading import Lock
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import (
    User,
    Session,
    Organization,
    Source,
    ScanJob,
    Document,
    DocumentVersion,
    Occurrence,
    Finding,
    Evidence,
    Incident,
    Investigation,
    ToolCall,
    Review,
    MonitoringCheck,
    EvaluationRun,
    now,
)
from app.security import current_user, scoped, verify_password, create_session
from app.api.schemas import LoginIn, OrganizationIn, SourceIn, ReviewIn, InvestigationIn
from app.api.middleware import RequestBodyLimitMiddleware
from app.connectors.policy import validate_url, local_repository
from app.detectors import availability, safe_text, sanitize
from app.parsers import supported
from app.workers.jobs import enqueue, run_scan

logging.basicConfig(level=logging.INFO, format="%(message)s")
# Prevent transport libraries from logging request metadata or full provider errors.
for name in ("httpx", "httpcore", "anthropic", "mcp", "fastmcp", "presidio-analyzer"):
    logging.getLogger(name).setLevel(logging.CRITICAL)


@asynccontextmanager
async def lifespan(app):
    root = settings().data_dir.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    (root / "uploads").mkdir(exist_ok=True, mode=0o700)
    yield


app = FastAPI(title="LeakLens AI", version="0.1.0", lifespan=lifespan)
app.add_middleware(RequestBodyLimitMiddleware)
login_attempts = OrderedDict()
login_attempts_lock = Lock()


def throttle_login(identity):
    now_seconds = time.monotonic()
    with login_attempts_lock:
        while login_attempts:
            first = next(iter(login_attempts))
            if login_attempts[first][-1] >= now_seconds - 60:
                break
            login_attempts.popitem(last=False)
        if identity not in login_attempts:
            if len(login_attempts) >= 4096:
                raise HTTPException(429, "Too many sign-in attempts; wait one minute")
            login_attempts[identity] = deque()
        attempts = login_attempts[identity]
        while attempts and attempts[0] < now_seconds - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many sign-in attempts; wait one minute")
        attempts.append(now_seconds)
        login_attempts.move_to_end(identity)


def record(row, exclude=()):
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {*exclude, "workspace_id"}
    }


def page(db, model, workspace, offset=0, limit=50, extra=()):
    query = select(model).where(model.workspace_id == workspace, *extra)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(model.created_at.desc()).offset(offset).limit(limit)).all()
    return {"items": [record(r) for r in rows], "total": total, "offset": offset, "limit": limit}


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != settings().allowed_origin.rstrip("/"):
            return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    response = await call_next(request)
    response.headers.update(
        {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        }
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's default error includes the rejected input; never echo submitted secrets.
    return JSONResponse(
        {"detail": safe_text("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors()))},
        status_code=422,
    )


@app.exception_handler(ValueError)
async def value_error(request, exc):
    return JSONResponse({"detail": safe_text(str(exc))}, status_code=400)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ready")
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


@app.post("/api/auth/login")
def login(payload: LoginIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    identity = request.client.host if request.client else "unknown"
    throttle_login(identity)
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    valid = verify_password(payload.password, user.password_hash if user else None)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect")
    token, csrf = create_session(db, user)
    response.set_cookie(
        "leaklens_session",
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        max_age=settings().session_hours * 3600,
        path="/",
    )
    return {"email": user.email, "csrf_token": csrf}


@app.get("/api/auth/me")
def me(request: Request, user=Depends(current_user)):
    return {
        "email": user.email,
        "csrf_token": request.state.session.csrf,
        "read_only": settings().public_read_only,
    }


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, user=Depends(current_user), db: DBSession = Depends(get_db)):
    db.delete(db.get(Session, request.state.session.id))
    db.commit()
    response.delete_cookie("leaklens_session", path="/")
    return {"ok": True}


@app.get("/api/organizations")
def organizations(user=Depends(current_user), db: DBSession = Depends(get_db)):
    return page(db, Organization, user.workspace_id, limit=100)


@app.post("/api/organizations", status_code=201)
def create_organization(payload: OrganizationIn, user=Depends(current_user), db: DBSession = Depends(get_db)):
    org = Organization(workspace_id=user.workspace_id, **payload.model_dump())
    db.add(org)
    db.commit()
    return record(org)


@app.put("/api/organizations/{organization_id}")
def update_organization(
    organization_id: str, payload: OrganizationIn, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    org = scoped(db, Organization, organization_id, user.workspace_id)
    for key, value in payload.model_dump().items():
        setattr(org, key, value)
    db.commit()
    return record(org)


@app.get("/api/sources")
def sources(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    return page(db, Source, user.workspace_id, offset, limit)


@app.post("/api/sources", status_code=201)
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
    db.commit()
    return record(source)


@app.post("/api/sources/{source_id}/check")
def check_source(source_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    source = scoped(db, Source, source_id, user.workspace_id)
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


def submit_scan(db, source, key=None):
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
        return active
    job = ScanJob(workspace_id=source.workspace_id, source_id=source.id, idempotency_key=key)
    db.add(job)
    db.commit()
    try:
        enqueue(run_scan, job.id)
    except Exception:
        job.status = "failed"
        job.errors = ["Worker queue unavailable; retry after restoring the queue"]
        db.commit()
    return job


@app.post("/api/sources/{source_id}/scans", status_code=202)
def start_scan(source_id: str, request: Request, user=Depends(current_user), db: DBSession = Depends(get_db)):
    source = scoped(db, Source, source_id, user.workspace_id)
    key = request.headers.get("idempotency-key")
    if key and len(key) > 100:
        raise HTTPException(400, "Idempotency key is too long")
    return record(submit_scan(db, source, key))


@app.post("/api/uploads", status_code=202)
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
                    raise HTTPException(413, "File exceeds the 10 MB limit")
                output.write(chunk)
        if not total:
            raise HTTPException(400, "File is empty")
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        db.rollback()
        raise
    finally:
        await file.close()
    return record(submit_scan(db, source))


@app.get("/api/scans")
def scans(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    return page(db, ScanJob, user.workspace_id, offset, limit)


@app.get("/api/scans/{job_id}")
def scan(job_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return record(scoped(db, ScanJob, job_id, user.workspace_id))


@app.post("/api/scans/{job_id}/cancel")
def cancel_scan(job_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    job = scoped(db, ScanJob, job_id, user.workspace_id)
    if job.status in {"queued", "running"}:
        job.cancel_requested = True
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = now()
        db.commit()
    return record(job)


@app.post("/api/scans/{job_id}/retry", status_code=202)
def retry_scan(job_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    job = scoped(db, ScanJob, job_id, user.workspace_id)
    if job.status in {"queued", "running"}:
        raise HTTPException(409, "The job is still active")
    return record(submit_scan(db, scoped(db, Source, job.source_id, user.workspace_id)))


@app.get("/api/incidents")
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
    return page(db, Incident, user.workspace_id, offset, limit, extra)


def incident_report(db, incident, workspace):
    document = scoped(db, Document, incident.document_id, workspace)
    related = []
    for link in incident.related:
        peer = db.scalar(
            select(Incident).where(
                Incident.document_id == link["document_id"], Incident.workspace_id == workspace
            )
        )
        related.append({**link, "incident_id": peer.id if peer else None})
    return {
        **record(incident),
        "related": related,
        "document": record(document, ("shingles", "content_hash")),
        "evidence": [
            record(e)
            for e in db.scalars(
                select(Evidence).where(
                    Evidence.document_id == document.id, Evidence.workspace_id == workspace
                )
            )
        ],
        "findings": [
            record(f, ("fingerprint",))
            for f in db.scalars(
                select(Finding).where(Finding.document_id == document.id, Finding.workspace_id == workspace)
            )
        ],
        "occurrences": [
            {
                **record(o, ("locator_hash",)),
                "source_name": db.get(Source, o.source_id).name,
                "access_context": db.get(Source, o.source_id).access_context,
            }
            for o in db.scalars(
                select(Occurrence).where(
                    Occurrence.document_id == document.id, Occurrence.workspace_id == workspace
                )
            )
        ],
        "versions": [
            record(v, ("locator_hash",))
            for v in db.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.id, DocumentVersion.workspace_id == workspace
                )
            )
        ],
        "reviews": [
            record(r)
            for r in db.scalars(
                select(Review)
                .where(Review.incident_id == incident.id, Review.workspace_id == workspace)
                .order_by(Review.created_at.desc())
            )
        ],
        "investigations": [
            record(r)
            for r in db.scalars(
                select(Investigation)
                .where(Investigation.incident_id == incident.id, Investigation.workspace_id == workspace)
                .order_by(Investigation.created_at.desc())
            )
        ],
    }


@app.get("/api/incidents/{incident_id}")
def incident_detail(incident_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return incident_report(db, scoped(db, Incident, incident_id, user.workspace_id), user.workspace_id)


@app.post("/api/incidents/{incident_id}/reviews", status_code=201)
def review(incident_id: str, payload: ReviewIn, user=Depends(current_user), db: DBSession = Depends(get_db)):
    incident = scoped(db, Incident, incident_id, user.workspace_id)
    review = Review(
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


@app.get("/api/incidents/{incident_id}/export")
def export(incident_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    report = incident_report(db, scoped(db, Incident, incident_id, user.workspace_id), user.workspace_id)
    return JSONResponse(
        sanitize({"schema_version": "1", "exported_at": now(), "redacted": True, "report": report}),
        headers={"Content-Disposition": f'attachment; filename="leaklens-{incident_id}.json"'},
    )


@app.post("/api/incidents/{incident_id}/investigations", status_code=202)
def investigate(
    incident_id: str, payload: InvestigationIn, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    incident = scoped(db, Incident, incident_id, user.workspace_id)
    if payload.mode == "live" and (settings().llm_mode != "live" or not settings().anthropic_api_key):
        raise HTTPException(
            409, "Live agent is not configured; enable it with server-side environment variables"
        )
    active = db.scalar(
        select(Investigation).where(
            Investigation.incident_id == incident.id, Investigation.status.in_(["queued", "running"])
        )
    )
    if active:
        return record(active)
    run = Investigation(
        workspace_id=user.workspace_id,
        incident_id=incident.id,
        mode=payload.mode,
        model=settings().llm_model if payload.mode == "live" else None,
    )
    db.add(run)
    db.commit()
    from app.agent.runner import run_investigation

    try:
        enqueue(run_investigation, run.id)
    except Exception:
        run.status = "failed"
        run.error = "Worker queue unavailable"
        db.commit()
    return record(run)


@app.get("/api/investigations/{run_id}")
def investigation(run_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    run = scoped(db, Investigation, run_id, user.workspace_id)
    calls = db.scalars(
        select(ToolCall)
        .where(ToolCall.investigation_id == run.id, ToolCall.workspace_id == user.workspace_id)
        .order_by(ToolCall.created_at)
    ).all()
    return {**record(run), "tool_calls": [record(c) for c in calls]}


@app.get("/api/monitoring/{occurrence_id}")
def monitoring(occurrence_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    scoped(db, Occurrence, occurrence_id, user.workspace_id)
    return page(
        db,
        MonitoringCheck,
        user.workspace_id,
        limit=100,
        extra=[MonitoringCheck.occurrence_id == occurrence_id],
    )


@app.get("/api/overview")
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
        "sources": count(Source),
        "source_issues": count(Source, Source.health.in_(["error", "partial", "failed"])),
        "recent_scans": page(db, ScanJob, w, limit=5)["items"],
        "trend": [{"date": date, "incidents": n} for date, n in reversed(trend)],
        "mode": "Live agent available"
        if settings().llm_mode == "live" and settings().anthropic_api_key
        else "LLM disabled",
    }


@app.get("/api/settings")
def configuration(user=Depends(current_user)):
    cfg = settings()
    return {
        "mode": cfg.llm_mode,
        "live_available": cfg.llm_mode == "live" and bool(cfg.anthropic_api_key),
        "model": cfg.llm_model if cfg.llm_mode == "live" else None,
        "detectors": availability(),
        "limits": {
            "max_file_mb": cfg.max_file_bytes // 1024 // 1024,
            "documents_per_scan": cfg.max_documents,
            "pdf_pages": cfg.max_pdf_pages,
            "csv_rows": cfg.max_csv_rows,
            "raw_retention_hours": cfg.raw_retention_hours,
            "agent_max_tools": cfg.agent_max_tools,
        },
        "read_only": cfg.public_read_only,
    }


@app.get("/api/evaluations")
def evaluations(user=Depends(current_user), db: DBSession = Depends(get_db)):
    return page(db, EvaluationRun, user.workspace_id)
