import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).isoformat()


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Scoped(Record):
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)


class Workspace(Record, Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(200))


class User(Scoped, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class Session(Record, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[str] = mapped_column(String(40))


class Organization(Scoped, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    domains: Mapped[list] = mapped_column(JSON, default=list)
    reference_ids: Mapped[list] = mapped_column(JSON, default=list)
    importance: Mapped[str] = mapped_column(String(20), default="normal")


class Source(Scoped, Base):
    __tablename__ = "sources"
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    access_context: Mapped[str] = mapped_column(String(30), default="supplied")
    health: Mapped[str] = mapped_column(String(30), default="unchecked")
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    last_checked: Mapped[str | None] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    archived_at: Mapped[str | None] = mapped_column(String(40))


class SourceEvent(Scoped, Base):
    __tablename__ = "source_events"
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(30))
    revision: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("source_id", "revision"),)


class ScanJob(Scoped, Base):
    __tablename__ = "scan_jobs"
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(30), default="queued")
    phase: Mapped[str] = mapped_column(String(80), default="queued")
    processed: Mapped[int] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    attempts: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[str | None] = mapped_column(String(40))
    finished_at: Mapped[str | None] = mapped_column(String(40))
    heartbeat_at: Mapped[str | None] = mapped_column(String(40))
    idempotency_key: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)


class Document(Scoped, Base):
    __tablename__ = "documents"
    content_hash: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(50), default="unknown")
    redacted_text: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    shingles: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (UniqueConstraint("workspace_id", "content_hash"),)


class DocumentVersion(Scoped, Base):
    __tablename__ = "document_versions"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    previous_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    locator_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[str] = mapped_column(String(80), default="current")
    __table_args__ = (UniqueConstraint("source_id", "locator_hash", "document_id", "revision"),)


class Occurrence(Scoped, Base):
    __tablename__ = "source_occurrences"
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    locator: Mapped[str] = mapped_column(Text)
    locator_hash: Mapped[str] = mapped_column(String(64))
    revision: Mapped[str] = mapped_column(String(80), default="current")
    state: Mapped[str] = mapped_column(String(40), default="observed")
    access_context: Mapped[str] = mapped_column(String(30), default="supplied", server_default="supplied")
    first_observed: Mapped[str] = mapped_column(String(40), default=now)
    last_observed: Mapped[str] = mapped_column(String(40), default=now)
    last_job_id: Mapped[str] = mapped_column(String(36))
    __table_args__ = (UniqueConstraint("source_id", "locator_hash", "revision", "document_id"),)


class Evidence(Scoped, Base):
    __tablename__ = "evidence"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    location: Mapped[dict] = mapped_column(JSON)
    excerpt: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Finding(Scoped, Base):
    __tablename__ = "findings"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"))
    finding_type: Mapped[str] = mapped_column(String(60))
    detector: Mapped[str] = mapped_column(String(100))
    detector_version: Mapped[str] = mapped_column(String(40))
    score: Mapped[float | None]
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    placeholder: Mapped[bool] = mapped_column(default=False)


class Incident(Scoped, Base):
    __tablename__ = "incidents"
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), unique=True)
    title: Mapped[str] = mapped_column(String(350))
    category: Mapped[str] = mapped_column(String(50))
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(40), default="open")
    summary: Mapped[str] = mapped_column(Text)
    attribution: Mapped[list] = mapped_column(JSON, default=list)
    related: Mapped[list] = mapped_column(JSON, default=list)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[str] = mapped_column(String(40), default=now)


class Investigation(Scoped, Base):
    __tablename__ = "investigations"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(40), default="investigation-v1")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(String(40))


class ToolCall(Scoped, Base):
    __tablename__ = "tool_calls"
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"))
    name: Mapped[str] = mapped_column(String(100))
    arguments: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    duration_ms: Mapped[int]
    success: Mapped[bool]


class Review(Scoped, Base):
    __tablename__ = "reviews"
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(String(20))


class MonitoringCheck(Scoped, Base):
    __tablename__ = "monitoring_checks"
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    job_id: Mapped[str] = mapped_column(ForeignKey("scan_jobs.id"))
    occurrence_id: Mapped[str] = mapped_column(ForeignKey("source_occurrences.id"))
    state: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)


class EvaluationRun(Scoped, Base):
    __tablename__ = "evaluation_runs"
    dataset_version: Mapped[str] = mapped_column(String(100))
    results: Mapped[dict] = mapped_column(JSON)
