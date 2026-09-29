"""Internal MCP server. Immutable workspace/case scope comes from its parent worker."""

import os
from sqlalchemy import select
from fastmcp import FastMCP
from app.db import SessionLocal
from app.models import Incident, Document, Evidence, Occurrence, MonitoringCheck, now
from app.detectors import sanitize

mcp = FastMCP("LeakLens scoped evidence")


def scope(db):
    workspace = os.environ["LEAKLENS_MCP_WORKSPACE"]
    case = db.scalar(
        select(Incident).where(
            Incident.id == os.environ["LEAKLENS_MCP_CASE"], Incident.workspace_id == workspace
        )
    )
    if case is None:
        raise ValueError("Case is inaccessible")
    allowed = {case.document_id, *(r["document_id"] for r in case.related)}
    return workspace, case, allowed


def document(db, document_id):
    workspace, case, allowed = scope(db)
    if document_id not in allowed:
        raise ValueError("Document is outside this investigation")
    doc = db.scalar(select(Document).where(Document.id == document_id, Document.workspace_id == workspace))
    if doc is None:
        raise ValueError("Document is inaccessible")
    return workspace, case, doc


def envelope(data, evidence_ids=(), complete=True, error=None):
    return sanitize(
        {
            "data": data,
            "evidence_ids": list(evidence_ids),
            "timestamp": now(),
            "complete": complete,
            "error": error,
        }
    )


@mcp.tool
def get_document_metadata(document_id: str) -> dict:
    """Get stored metadata for a document in this investigation."""
    with SessionLocal() as db:
        workspace, _, doc = document(db, document_id)
        ids = db.scalars(
            select(Evidence.id).where(Evidence.document_id == doc.id, Evidence.workspace_id == workspace)
        ).all()
        return envelope(
            {
                "document_id": doc.id,
                "name": doc.name,
                "category": doc.category,
                "metadata": doc.metadata_json,
            },
            ids,
            not doc.metadata_json.get("coverage_warnings"),
        )


@mcp.tool
def get_redacted_content(document_id: str, bounded_location: int = 1) -> dict:
    """Read up to 30 redacted lines starting at a one-based line number, capped at 6000 characters."""
    if bounded_location < 1 or bounded_location > 200000:
        raise ValueError("Invalid location")
    with SessionLocal() as db:
        workspace, _, doc = document(db, document_id)
        lines = doc.redacted_text.splitlines()
        evidence = db.scalars(
            select(Evidence).where(Evidence.document_id == doc.id, Evidence.workspace_id == workspace)
        ).all()
        ids = [
            e.id for e in evidence if bounded_location <= e.location.get("line", 0) < bounded_location + 30
        ]
        chunk = "\n".join(lines[bounded_location - 1 : bounded_location + 29])
        return envelope(
            {
                "document_id": doc.id,
                "start_line": bounded_location,
                "text": chunk[:6000],
                "total_lines": len(lines),
            },
            ids,
            len(chunk) <= 6000 and bounded_location + 29 >= len(lines),
        )


@mcp.tool
def find_company_evidence(document_id: str) -> dict:
    """Get organization signals and uncertainty; host identity does not establish ownership."""
    with SessionLocal() as db:
        workspace, _, doc = document(db, document_id)
        case = db.scalar(
            select(Incident).where(Incident.document_id == doc.id, Incident.workspace_id == workspace)
        )
        associations = case.attribution if case else []
        return envelope(associations, [e for a in associations for e in a["evidence_ids"]])


@mcp.tool
def find_related_documents(document_id: str) -> dict:
    """Get explainable near-duplicate and repeated-secret candidate links."""
    with SessionLocal() as db:
        workspace, _, doc = document(db, document_id)
        case = db.scalar(
            select(Incident).where(Incident.document_id == doc.id, Incident.workspace_id == workspace)
        )
        return envelope(case.related[:20] if case else [], complete=not case or len(case.related) <= 20)


@mcp.tool
def get_exposure_history(source_occurrence_id: str) -> dict:
    """Get observed, not observed, or unknown monitoring results for an authorized occurrence."""
    with SessionLocal() as db:
        workspace, _, allowed = scope(db)
        occurrence = db.scalar(
            select(Occurrence).where(
                Occurrence.id == source_occurrence_id, Occurrence.workspace_id == workspace
            )
        )
        if occurrence is None or occurrence.document_id not in allowed:
            raise ValueError("Occurrence is outside this investigation")
        checks = db.scalars(
            select(MonitoringCheck)
            .where(MonitoringCheck.occurrence_id == occurrence.id, MonitoringCheck.workspace_id == workspace)
            .order_by(MonitoringCheck.created_at.desc())
            .limit(20)
        ).all()
        return envelope(
            [{"id": c.id, "state": c.state, "timestamp": c.created_at, "detail": c.detail} for c in checks],
            complete=len(checks) < 20,
        )


@mcp.tool
def search_remediation_guidance(finding_type: str) -> dict:
    """Search curated local guidance; never authenticate with a discovered credential."""
    guidance = {
        "SUSPECTED_SECRET": [
            "Ask the asset owner to confirm scope.",
            "Revoke or rotate through the authorized owner; do not test the value.",
            "Remove exposed copies and review audit logs; removing a file does not revoke a credential.",
        ],
        "EMAIL_ADDRESS": [
            "Verify business context and permitted access.",
            "Restrict distribution and notify the appropriate internal privacy contact.",
        ],
        "PHONE_NUMBER": ["Verify the record scope and restrict unintended access."],
        "CREDIT_CARD": ["Restrict access and escalate to the authorized security and payment-data owner."],
    }
    with SessionLocal() as db:
        scope(db)
    return envelope(
        {
            "finding_type": finding_type,
            "guidance_version": "guidance-v1",
            "steps": guidance.get(
                finding_type, ["Collect more authorized evidence and ask the asset owner to review."]
            ),
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
