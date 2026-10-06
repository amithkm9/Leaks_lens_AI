"""Versioned detector results; content identity and analyst decisions stay separate."""

import hashlib
import importlib.metadata
import json
import shutil
import subprocess
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select

from app import attribution, correlation, detectors, parsers
from app.config import settings
from app.models import Document, DocumentAnalysis, Organization, Review


@lru_cache(maxsize=8)
def _binary_version(binary, modified, size):
    try:
        result = subprocess.run([binary, "version"], capture_output=True, timeout=3, check=True)
        return result.stdout.decode().strip()[:40]
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return "unavailable"


def redaction_manifest():
    cfg = settings()
    binary = shutil.which("gitleaks")
    version = None
    if binary:
        info = Path(binary).stat()
        version = _binary_version(binary, info.st_mtime_ns, info.st_size)
    return {
        "parser": parsers.PARSER_VERSION,
        "pypdf": importlib.metadata.version("pypdf"),
        "custom": detectors.CUSTOM_VERSION,
        "presidio": detectors.availability()["presidio"],
        "gitleaks": version,
        "limits": {
            "bytes": cfg.max_file_bytes,
            "pages": cfg.max_pdf_pages,
            "rows": cfg.max_csv_rows,
            "chars": cfg.max_text_chars,
        },
    }


def organization_snapshot(db, workspace):
    return [
        {
            "id": org.id,
            "name": org.name,
            "aliases": sorted(org.aliases),
            "domains": sorted(org.domains),
            "reference_ids": sorted(org.reference_ids),
            "importance": org.importance,
        }
        for org in db.scalars(
            select(Organization).where(Organization.workspace_id == workspace).order_by(Organization.id)
        )
    ]


def profile_hash(profiles):
    return hashlib.sha256(json.dumps(profiles, sort_keys=True).encode()).hexdigest()


def versions(name, profiles, access):
    return {
        "redaction": redaction_manifest(),
        "format": Path(name).suffix.lower() or Path(name).name,
        "attribution": attribution.ATTRIBUTION_VERSION,
        "policy": correlation.POLICY_VERSION,
        "organization_profiles": profile_hash(profiles),
        "access_context": access,
    }


def get_analysis(db, document, revision=None):
    return db.scalar(
        select(DocumentAnalysis).where(
            DocumentAnalysis.document_id == document.id,
            DocumentAnalysis.workspace_id == document.workspace_id,
            DocumentAnalysis.revision == (revision if revision is not None else document.analysis_revision),
        )
    )


def restricted(analysis, manifest=None):
    return (
        analysis is None
        or analysis.redaction_status != "available"
        or analysis.versions.get("redaction") != (manifest if manifest is not None else redaction_manifest())
    )


def analysis_metadata(analysis, current_revision, profiles):
    blocked = restricted(analysis)
    reasons = []
    if analysis.versions.get("legacy"):
        reasons.append("Original pipeline and organization-profile versions were not recorded")
    elif analysis.versions.get("redaction") != redaction_manifest():
        reasons.append("Parser, detector versions, or extraction limits have changed")
    if analysis.versions.get("organization_profiles") != profile_hash(profiles):
        reasons.append("Organization profiles have changed or their original versions are unknown")
    if analysis.versions.get("attribution") != attribution.ATTRIBUTION_VERSION:
        reasons.append("Attribution rules have changed or their original version is unknown")
    if analysis.versions.get("policy") != correlation.POLICY_VERSION:
        reasons.append("Priority policy has changed or its original version is unknown")
    return {
        "id": analysis.id,
        "revision": analysis.revision,
        "current": analysis.revision == current_revision,
        "created_at": analysis.created_at,
        "reason": detectors.safe_text(analysis.reason),
        "requested_by": analysis.requested_by,
        "job_id": analysis.job_id,
        "versions": analysis.versions,
        "organization_count": len(analysis.organization_snapshot),
        "restricted": blocked,
        "freshness": "stale" if reasons else "current",
        "freshness_reasons": reasons,
        "finding_count": analysis.metadata_json.get("finding_count"),
    }


def case_for_analysis(incident, analysis, scope_snapshot=None):
    fields = {c.name: getattr(incident, c.name) for c in incident.__table__.columns}
    fields.update(
        {key: deepcopy(getattr(analysis, key)) for key in ("category", "summary", "attribution", "policy")}
    )
    fields.update(
        analysis_revision=analysis.revision,
        scope_snapshot=scope_snapshot or {},
        related=deepcopy(analysis.related),
    )
    return SimpleNamespace(**fields)


def capture_scope(db, incident, analysis):
    allowed = {incident.document_id: analysis.revision}
    links = deepcopy(incident.related)
    for link in links:
        doc = db.scalar(
            select(Document).where(
                Document.id == link["document_id"], Document.workspace_id == incident.workspace_id
            )
        )
        if doc:
            peer = get_analysis(db, doc, link.get("analysis_revision"))
            if not restricted(peer):
                allowed[doc.id] = peer.revision
    return {"analyses": allowed, "related": [link for link in links if link["document_id"] in allowed]}


def review_state(db, incident, analysis):
    status, priority = "open", analysis.policy.get("priority", "low")
    actions = {
        "confirm": "confirmed",
        "dismiss": "dismissed",
        "request_context": "needs_context",
        "remediate": "remediated",
        "reopen": "open",
    }
    for review in db.scalars(
        select(Review)
        .where(
            Review.incident_id == incident.id,
            Review.analysis_revision == analysis.revision,
            Review.workspace_id == incident.workspace_id,
        )
        .order_by(Review.created_at, Review.id)
    ):
        status = actions.get(review.action, status)
        priority = review.priority or priority
    return status, priority


def guard_incident_list(db, result, workspace):
    # One bounded join replaces two extra queries per incident in queue/dashboard lists.
    document_ids = [item["document_id"] for item in result["items"]]
    if not document_ids:
        return result
    rows = db.execute(
        select(Document, DocumentAnalysis)
        .outerjoin(
            DocumentAnalysis,
            (DocumentAnalysis.document_id == Document.id)
            & (DocumentAnalysis.revision == Document.analysis_revision)
            & (DocumentAnalysis.workspace_id == Document.workspace_id),
        )
        .where(Document.workspace_id == workspace, Document.id.in_(document_ids))
    ).all()
    analyses = {doc.id: (doc.analysis_revision, analysis) for doc, analysis in rows}
    manifest = redaction_manifest()
    for item in result["items"]:
        revision, analysis = analyses.get(item["document_id"], (0, None))
        item["analysis_revision"] = revision
        item["analysis_restricted"] = restricted(analysis, manifest)
        if item["analysis_restricted"]:
            item.update(
                summary="Analysis requires refresh before evidence can be displayed.",
                attribution=[],
                related=[],
                policy={},
            )
    return result
