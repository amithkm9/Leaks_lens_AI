import logging
import time
from collections import OrderedDict, deque
from threading import Lock
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text, update
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import (
    User,
    Session,
    Organization,
    Source,
    SourceEvent,
    ScanJob,
    Document,
    DocumentVersion,
    DocumentAnalysis,
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
from app.api.schemas import (
    LoginIn,
    OrganizationIn,
    SourceIn,
    SourceUpdate,
    SourceArchiveIn,
    ReviewIn,
    InvestigationIn,
    SourceReanalysisIn,
    IncidentReanalysisIn,
)
from app.api.middleware import RequestBodyLimitMiddleware
from app.connectors.policy import validate_url, local_repository
from app.detectors import availability, safe_text, sanitize
from app.parsers import supported
from app.workers.jobs import enqueue, run_scan
from app.analysis import (
    get_analysis,
    restricted,
    analysis_metadata,
    organization_snapshot,
    review_state,
    capture_scope,
    guard_incident_list,
)
from app.sources import snapshot, record_event, lock_source, require_current, require_active, require_idle

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
    rows = db.scalars(
        query.order_by(model.created_at.desc(), model.id.desc()).offset(offset).limit(limit)
    ).all()
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
        {
            "detail": safe_text(
                "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors())
            )
        },
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
    db.flush()
    record_event(db, source, "created", user.id)
    db.commit()
    return record(source)


@app.put("/api/sources/{source_id}")
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


@app.post("/api/sources/{source_id}/archive")
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


@app.get("/api/sources/{source_id}/history")
def source_history(
    source_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    scoped(db, Source, source_id, user.workspace_id)
    return page(db, SourceEvent, user.workspace_id, offset, limit, [SourceEvent.source_id == source_id])


@app.post("/api/sources/{source_id}/check")
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


@app.get("/api/scans")
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


@app.post("/api/sources/{source_id}/reanalyses", status_code=202)
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


def current_analysis(db, incident, expected=None, require_available=True):
    db.execute(
        update(Document)
        .where(Document.id == incident.document_id)
        .values(analysis_revision=Document.analysis_revision)
        .execution_options(synchronize_session=False)
    )
    document = scoped(db, Document, incident.document_id, incident.workspace_id)
    db.refresh(document)
    db.refresh(incident)
    if expected is not None and expected != document.analysis_revision:
        raise HTTPException(409, "Analysis changed. Refresh the incident before making this decision.")
    analysis = get_analysis(db, document)
    if require_available and restricted(analysis):
        raise HTTPException(
            409, "Analysis is restricted; reanalyze original bytes before reviewing or investigating"
        )
    return document, analysis


@app.post("/api/incidents/{incident_id}/reanalyses", status_code=202)
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
    return guard_incident_list(
        db, page(db, Incident, user.workspace_id, offset, limit, extra), user.workspace_id
    )


def occurrence_record(db, occurrence):
    source = db.get(Source, occurrence.source_id)
    return {
        **record(occurrence, ("locator_hash",)),
        "source_name": source.name,
        "source_archived": bool(source.archived_at),
        "reanalysis_available": not source.archived_at
        and (source.kind != "upload" or (settings().data_dir.resolve() / "uploads" / source.id).is_file()),
    }


def incident_report(db, incident, workspace, revision=None):
    document = scoped(db, Document, incident.document_id, workspace)
    analysis = get_analysis(db, document, revision)
    if analysis is None:
        raise HTTPException(404, "Analysis revision not found")
    blocked = restricted(analysis)
    profiles = organization_snapshot(db, workspace)
    status, priority = review_state(db, incident, analysis)
    links = incident.related if analysis.revision == document.analysis_revision else analysis.related
    related = []
    if not blocked:
        for link in links:
            peer = db.scalar(
                select(Incident).where(
                    Incident.document_id == link["document_id"], Incident.workspace_id == workspace
                )
            )
            related.append({**link, "incident_id": peer.id if peer else None})
    analyses = db.scalars(
        select(DocumentAnalysis)
        .where(DocumentAnalysis.document_id == document.id, DocumentAnalysis.workspace_id == workspace)
        .order_by(DocumentAnalysis.revision.desc())
    ).all()
    return {
        **record(incident),
        "status": status,
        "priority": priority,
        "category": analysis.category,
        "analysis_revision": analysis.revision,
        "current_analysis_revision": document.analysis_revision,
        "analysis": analysis_metadata(analysis, document.analysis_revision, profiles),
        "analyses": [analysis_metadata(a, document.analysis_revision, profiles) for a in analyses],
        "summary": "Analysis requires refresh before evidence can be displayed."
        if blocked
        else analysis.summary,
        "attribution": [] if blocked else analysis.attribution,
        "policy": {} if blocked else analysis.policy,
        "related": related,
        "document": {
            **record(document, ("shingles", "content_hash", "redacted_text", "metadata_json")),
            "name": analysis.input_name,
            "category": analysis.category,
            "analysis_revision": analysis.revision,
            "redacted_text": "" if blocked else analysis.redacted_text,
            "metadata_json": {} if blocked else analysis.metadata_json,
        },
        "evidence": []
        if blocked
        else [
            record(e)
            for e in db.scalars(
                select(Evidence).where(
                    Evidence.document_id == document.id,
                    Evidence.workspace_id == workspace,
                    Evidence.analysis_revision == analysis.revision,
                )
            )
        ],
        "findings": []
        if blocked
        else [
            record(f, ("fingerprint",))
            for f in db.scalars(
                select(Finding).where(
                    Finding.document_id == document.id,
                    Finding.workspace_id == workspace,
                    Finding.analysis_revision == analysis.revision,
                )
            )
        ],
        "occurrences": [
            occurrence_record(db, o)
            for o in db.scalars(
                select(Occurrence).where(
                    Occurrence.document_id == document.id, Occurrence.workspace_id == workspace
                )
            )
        ],
        "observation_scope": "Latest observations, independent of the selected analysis revision",
        "versions": [
            record(v, ("locator_hash",))
            for v in db.scalars(
                select(DocumentVersion).where(
                    DocumentVersion.document_id == document.id, DocumentVersion.workspace_id == workspace
                )
            )
        ],
        "reviews": [
            (
                {**record(r), "reason": "Historical text restricted pending redaction verification"}
                if blocked
                else record(r)
            )
            for r in db.scalars(
                select(Review)
                .where(
                    Review.incident_id == incident.id,
                    Review.workspace_id == workspace,
                    Review.analysis_revision == analysis.revision,
                )
                .order_by(Review.created_at.desc())
            )
        ],
        "investigations": [
            investigation_record(db, r)
            for r in db.scalars(
                select(Investigation)
                .where(
                    Investigation.incident_id == incident.id,
                    Investigation.workspace_id == workspace,
                    Investigation.analysis_revision == analysis.revision,
                )
                .order_by(Investigation.created_at.desc())
            )
        ],
    }


def investigation_record(db, run):
    incident = db.get(Incident, run.incident_id)
    document = db.get(Document, incident.document_id)
    blocked = restricted(get_analysis(db, document, run.analysis_revision))
    # A result may quote any document that the agent was allowed to retrieve.
    for doc_id, revision in run.scope_snapshot.get("analyses", {}).items():
        peer = db.scalar(
            select(Document).where(Document.id == doc_id, Document.workspace_id == run.workspace_id)
        )
        if peer is None or restricted(get_analysis(db, peer, revision)):
            blocked = True
    result = record(run)
    result["restricted"] = blocked
    if blocked:
        result.update(
            result={},
            error="Historical investigation output is restricted; request a fresh analysis.",
            scope_snapshot={},
        )
    return result


@app.get("/api/incidents/{incident_id}")
def incident_detail(
    incident_id: str,
    analysis_revision: int | None = Query(None, ge=1),
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    return incident_report(
        db, scoped(db, Incident, incident_id, user.workspace_id), user.workspace_id, analysis_revision
    )


@app.post("/api/incidents/{incident_id}/reviews", status_code=201)
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


@app.get("/api/incidents/{incident_id}/export")
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


@app.post("/api/incidents/{incident_id}/investigations", status_code=202)
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
    result = investigation_record(db, run)
    return {**result, "tool_calls": [] if result["restricted"] else [record(c) for c in calls]}


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
        "sources": count(Source, Source.archived_at.is_(None)),
        "source_issues": count(
            Source, Source.archived_at.is_(None), Source.health.in_(["error", "partial", "failed"])
        ),
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
            "max_file_bytes": cfg.max_file_bytes,
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
