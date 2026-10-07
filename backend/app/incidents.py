"""Revision-aware reports and analyst mutation guards."""

from fastapi import HTTPException
from sqlalchemy import select, update

from app.analysis import (
    analysis_metadata,
    get_analysis,
    organization_snapshot,
    restricted,
    review_state,
)
from app.config import settings
from app.models import (
    Document,
    DocumentAnalysis,
    DocumentVersion,
    Evidence,
    Finding,
    Incident,
    Investigation,
    Occurrence,
    RemediationTask,
    Review,
    Source,
)
from app.remediation import task_page
from app.security import scoped
from app.serialization import record


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
        "remediation": task_page(
            db,
            workspace,
            limit=100,
            extra=[
                RemediationTask.incident_id == incident.id,
                RemediationTask.analysis_revision == analysis.revision,
            ],
        ),
        "remediation_scope": "Latest task state for the selected analysis; analyst verification does not change incident status. Lists are paginated.",
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
