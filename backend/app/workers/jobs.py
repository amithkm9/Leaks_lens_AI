import json
import logging
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import select, update
from app.config import settings
from app.db import SessionLocal
from app.models import (
    ScanJob,
    Source,
    Document,
    DocumentVersion,
    Occurrence,
    DocumentAnalysis,
    MonitoringCheck,
    now,
)
from app.connectors import Collection, Item
from app.connectors import git, http
from app.detectors import fingerprint, safe_text
from app.analysis import get_analysis, organization_snapshot, versions
from app.workers.analysis import analyze_document

logger = logging.getLogger("leaklens.jobs")
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="leaklens-worker")


def enqueue(function, record_id):
    if settings().job_mode == "rq":
        from redis import Redis
        from rq import Queue

        Queue("leaklens", connection=Redis.from_url(settings().redis_url)).enqueue(
            function, record_id, job_timeout=900, result_ttl=3600
        )
    else:
        executor.submit(function, record_id)


def is_cancelled(job_id):
    with SessionLocal() as db:
        job = db.get(ScanJob, job_id)
        return not job or job.cancel_requested


def ingest(db, job, source, item):
    digest = fingerprint(item.path.read_bytes().hex())
    document = db.scalar(
        select(Document).where(Document.workspace_id == job.workspace_id, Document.content_hash == digest)
    )
    if document is None:
        document = Document(
            workspace_id=job.workspace_id, content_hash=digest, name=safe_text(item.name), analysis_revision=0
        )
        db.add(document)
        db.flush()
    else:
        # Serialize revisions for the same content, even when found on different sources.
        db.execute(
            update(Document)
            .where(Document.id == document.id)
            .values(analysis_revision=Document.analysis_revision)
            .execution_options(synchronize_session=False)
        )
        db.refresh(document)
    analysis = get_analysis(db, document)
    request = job.analysis_request
    same_job = db.scalar(
        select(DocumentAnalysis).where(
            DocumentAnalysis.document_id == document.id, DocumentAnalysis.job_id == job.id
        )
    )
    if request.get("document_id") == document.id and not same_job:
        if request["expected_revision"] != document.analysis_revision:
            raise ValueError(
                "Analysis changed after this request; refresh the incident and request reanalysis again"
            )
    profiles = organization_snapshot(db, job.workspace_id)
    access = source.access_context
    if db.scalar(
        select(Occurrence.id)
        .where(Occurrence.document_id == document.id, Occurrence.access_context == "public_observed")
        .limit(1)
    ):
        access = "public_observed"
    manifest = versions(item.name, profiles, access)
    if not same_job and (analysis is None or request or analysis.versions != manifest):
        analysis = analyze_document(db, job, item, document, manifest, profiles)
    else:
        analysis = same_job or analysis
    warnings = list(analysis.metadata_json.get("coverage_warnings", []))
    locator_hash = fingerprint(item.locator)
    occurrence = db.scalar(
        select(Occurrence).where(
            Occurrence.source_id == source.id,
            Occurrence.locator_hash == locator_hash,
            Occurrence.revision == item.revision,
            Occurrence.document_id == document.id,
        )
    )
    if occurrence is None:
        previous = db.scalar(
            select(Occurrence)
            .where(
                Occurrence.source_id == source.id,
                Occurrence.locator_hash == locator_hash,
                Occurrence.revision == item.revision,
            )
            .order_by(Occurrence.last_observed.desc())
        )
        occurrence = Occurrence(
            workspace_id=job.workspace_id,
            source_id=source.id,
            document_id=document.id,
            locator=safe_text(item.locator),
            locator_hash=locator_hash,
            revision=item.revision,
            last_job_id=job.id,
        )
        db.add(occurrence)
        db.add(
            DocumentVersion(
                workspace_id=job.workspace_id,
                document_id=document.id,
                previous_document_id=previous.document_id if previous else None,
                source_id=source.id,
                locator_hash=locator_hash,
                revision=item.revision,
            )
        )
        if previous and item.revision == "current":
            previous.state = "superseded"
    occurrence.last_observed = now()
    occurrence.last_job_id = job.id
    occurrence.access_context = source.access_context
    occurrence.state = "supplied" if source.kind == "upload" else "observed"
    db.flush()
    db.add(
        MonitoringCheck(
            workspace_id=job.workspace_id,
            source_id=source.id,
            job_id=job.id,
            occurrence_id=occurrence.id,
            state=occurrence.state,
            detail="Content supplied" if source.kind == "upload" else "Observed on this successful check",
        )
    )
    return list(dict.fromkeys(warnings))


def run_scan(job_id):
    start = time.monotonic()
    with SessionLocal() as db:
        claimed = db.execute(
            update(ScanJob)
            .where(ScanJob.id == job_id, ScanJob.status == "queued")
            .values(status="running", started_at=now(), heartbeat_at=now())
        )
        db.commit()
        if claimed.rowcount != 1:
            return
        job = db.get(ScanJob, job_id)
        source = db.get(Source, job.source_id)
        captured = job.source_snapshot
        scan_source = SimpleNamespace(
            id=source.id,
            workspace_id=source.workspace_id,
            kind=captured.get("kind", source.kind),
            config=captured.get("config", source.config),
            access_context=captured.get("access_context", source.access_context),
        )
        job.attempts += 1
        db.commit()
        try:
            cfg = settings()
            staging_root = cfg.data_dir.resolve() / "staging"
            staging_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            with tempfile.TemporaryDirectory(dir=staging_root) as directory:
                staging = Path(directory)
                job.phase = "collecting"
                db.commit()
                if scan_source.kind == "upload":
                    path = cfg.data_dir.resolve() / "uploads" / source.id
                    if not path.is_file():
                        raise ValueError("Raw upload has expired; upload the file again to reprocess")
                    collection = Collection(
                        items=[Item(path, scan_source.config["filename"], scan_source.config["filename"])]
                    )
                elif scan_source.kind == "git":
                    collection = git.collect(scan_source.config, staging, lambda: is_cancelled(job.id))
                else:
                    known = db.scalars(
                        select(Occurrence.locator)
                        .where(Occurrence.source_id == source.id, Occurrence.state != "superseded")
                        .limit(cfg.max_documents)
                    ).all()
                    collection = http.collect(
                        {**scan_source.config, "known_urls": list(known)},
                        staging,
                        lambda: is_cancelled(job.id),
                    )
                target = job.analysis_request.get("document_id")
                if target:
                    original = db.scalar(
                        select(Document).where(
                            Document.id == target, Document.workspace_id == job.workspace_id
                        )
                    )
                    collection.items = [
                        item
                        for item in collection.items
                        if original and fingerprint(item.path.read_bytes().hex()) == original.content_hash
                    ]
                    if not collection.items:
                        raise ValueError(
                            "Original bytes were not available on this source; upload the original file or choose another authorized source"
                        )
                job.total = len(collection.items)
                job.errors = collection.errors
                job.warnings = collection.warnings
                db.commit()
                for item in collection.items:
                    if is_cancelled(job.id):
                        break
                    job.phase = "detecting and redacting"
                    job.heartbeat_at = now()
                    db.commit()
                    try:
                        with db.begin_nested():
                            warnings = ingest(db, job, scan_source, item)
                        job.warnings = list(dict.fromkeys([*job.warnings, *warnings]))
                        job.processed += 1
                    except Exception as exc:
                        message = (
                            str(exc)
                            if isinstance(exc, ValueError)
                            else f"Processing failed ({type(exc).__name__})"
                        )
                        job.errors = [*job.errors, safe_text(message)]
                        collection.complete = False
                    db.commit()
                db.refresh(job)
                cancelled = job.cancel_requested
                job.status = (
                    "cancelled"
                    if cancelled
                    else "partial"
                    if job.errors or job.warnings or not collection.complete
                    else "completed"
                )
                job.phase = "finished"
                job.finished_at = now()
                source.health = (
                    "error"
                    if job.errors and not job.processed
                    else "partial"
                    if job.status == "partial"
                    else job.status
                )
                source.last_checked = now()
                if not target:
                    source.checkpoint = collection.checkpoint
                if scan_source.kind != "upload" and not cancelled and not target:
                    prior = db.scalars(
                        select(Occurrence).where(
                            Occurrence.source_id == source.id,
                            Occurrence.last_job_id != job.id,
                            Occurrence.state != "superseded",
                        )
                    ).all()
                    for occurrence in prior:
                        # Absence requires a successful direct 404/410, or a complete current Git inventory.
                        direct_absent = occurrence.locator_hash in {fingerprint(u) for u in collection.absent}
                        git_absent = (
                            scan_source.kind == "git"
                            and occurrence.revision == "current"
                            and collection.complete
                            and not job.errors
                        )
                        state = "not_observed" if direct_absent or git_absent else "unknown"
                        if scan_source.kind == "http" and not direct_absent:
                            state = "unknown"
                        occurrence.state = state
                        db.add(
                            MonitoringCheck(
                                workspace_id=job.workspace_id,
                                source_id=source.id,
                                job_id=job.id,
                                occurrence_id=occurrence.id,
                                state=state,
                                detail="Not observed on latest successful check; does not prove deletion or revocation"
                                if state == "not_observed"
                                else "Not verified this run; collection failure, limits, or link discovery cannot prove disappearance",
                            )
                        )
                db.commit()
        except Exception as exc:
            db.rollback()
            job = db.get(ScanJob, job_id)
            job.status = "failed"
            job.phase = "finished"
            job.errors = [
                safe_text(str(exc)) if isinstance(exc, ValueError) else f"Scan failed ({type(exc).__name__})"
            ]
            job.finished_at = now()
            source = db.get(Source, job.source_id)
            source.health = "error"
            source.last_checked = now()
            db.commit()
        logger.info(
            json.dumps(
                {
                    "event": "scan_finished",
                    "job_id": job.id,
                    "status": job.status,
                    "processed": job.processed,
                    "errors": len(job.errors),
                    "duration_seconds": round(time.monotonic() - start, 3),
                }
            )
        )


def purge_raw():
    root = settings().data_dir.resolve()
    cutoff = time.time() - settings().raw_retention_hours * 3600
    removed = 0
    for folder in (root / "uploads", root / "staging"):
        if not folder.exists():
            continue
        for path in folder.iterdir():
            if path.stat().st_mtime < cutoff:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                removed += 1
    return removed
