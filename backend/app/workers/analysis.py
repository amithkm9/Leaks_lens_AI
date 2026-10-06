"""Create one analysis revision from original bytes inside the ingestion transaction."""

from copy import deepcopy
from types import SimpleNamespace
from sqlalchemy import select
from app.models import Document, DocumentAnalysis, Evidence, Finding, Incident, now
from app.detectors import detect, safe_text
from app.parsers import parse_file
from app.attribution import attribute, categorize
from app.correlation import shingles, similarity, priority


def evidence_excerpt(text, line):
    lines = text.split("\n")
    return "\n".join(lines[max(0, line - 2) : line + 1])[:1500]


def analyze_document(db, job, item, document, manifest, profiles):
    parsed = parse_file(item.path, item.name)
    raw = parsed["text"]
    redacted, hits, detector_warnings = detect(raw)
    warnings = parsed["warnings"] + detector_warnings
    attributions = attribute(raw, [SimpleNamespace(**profile) for profile in profiles])
    category = categorize(raw, item.name, hits)
    revision = document.analysis_revision + 1
    metadata = {
        **parsed["metadata"],
        "coverage_warnings": warnings,
        "synthetic": "synthetic" in raw[:300].lower(),
        "finding_count": len(hits),
    }
    document.category, document.redacted_text = category, redacted
    document.metadata_json, document.shingles = metadata, shingles(redacted)
    document.analysis_revision = revision
    for hit in hits:
        line = raw[: hit["start"]].count("\n") + 1
        ev = Evidence(
            workspace_id=job.workspace_id,
            document_id=document.id,
            analysis_revision=revision,
            kind="detection",
            location={
                "line": line,
                "start": hit["start"],
                "end": hit["end"],
                "unit": "normalized_text_character",
            },
            excerpt=evidence_excerpt(redacted, line),
            details={"finding_type": hit["finding_type"]},
        )
        db.add(ev)
        db.flush()
        db.add(
            Finding(
                workspace_id=job.workspace_id,
                document_id=document.id,
                analysis_revision=revision,
                evidence_id=ev.id,
                **{
                    k: hit[k]
                    for k in (
                        "finding_type",
                        "detector",
                        "detector_version",
                        "score",
                        "fingerprint",
                        "placeholder",
                    )
                },
            )
        )
    for association in attributions:
        association["evidence_ids"] = []
        for signal in association["signals"]:
            ev = Evidence(
                workspace_id=job.workspace_id,
                document_id=document.id,
                analysis_revision=revision,
                kind="attribution",
                location={"line": signal["line"]},
                excerpt=evidence_excerpt(redacted, signal["line"]),
                details={
                    "signal": signal["kind"],
                    "approved_value": signal["value"],
                    "organization_id": association["organization_id"],
                },
            )
            db.add(ev)
            db.flush()
            association["evidence_ids"].append(ev.id)
    related = []
    if hits:
        others = db.scalars(
            select(Document)
            .where(
                Document.workspace_id == job.workspace_id,
                Document.id != document.id,
            )
            .order_by(Document.created_at.desc())
            .limit(500)
        ).all()
        for other in others:
            score = similarity(document.shingles, other.shingles)
            if score >= 0.6:
                related.append(
                    {
                        "document_id": other.id,
                        "name": other.name,
                        "analysis_revision": other.analysis_revision,
                        "method": "text_shingles",
                        "score": round(score, 3),
                        "caution": "Candidate relationship; identifiers and ownership require review",
                    }
                )
        fingerprints = [h["fingerprint"] for h in hits if h["finding_type"] == "SUSPECTED_SECRET"]
        if fingerprints:
            matches = db.scalars(
                select(Finding)
                .join(Document, Document.id == Finding.document_id)
                .where(
                    Finding.workspace_id == job.workspace_id,
                    Finding.fingerprint.in_(fingerprints),
                    Finding.document_id != document.id,
                    Finding.analysis_revision == Document.analysis_revision,
                )
            ).all()
            for match in matches:
                if not any(r["document_id"] == match.document_id for r in related):
                    other = db.get(Document, match.document_id)
                    related.append(
                        {
                            "document_id": other.id,
                            "name": other.name,
                            "analysis_revision": other.analysis_revision,
                            "method": "keyed_secret_fingerprint",
                            "score": None,
                            "caution": "Shared value does not establish shared ownership",
                        }
                    )
    policy = priority(hits, manifest["access_context"], attributions, parsed["metadata"].get("rows"))
    summary = (
        f"{len(hits)} detector candidate(s) require review. "
        if hits
        else "No detector candidates in this analysis. A negative result does not establish complete coverage or remediation. "
    )
    summary += (
        "Content was supplied; public exposure is not established."
        if manifest["access_context"] == "supplied"
        else "Observed on an explicitly configured source; review access context."
    )
    if not any(a["assessment"] == "supported" for a in attributions):
        summary += " Organization attribution is uncertain."
    analysis = DocumentAnalysis(
        workspace_id=job.workspace_id,
        document_id=document.id,
        revision=revision,
        job_id=job.id,
        requested_by=job.analysis_request.get("requested_by"),
        reason=safe_text(
            job.analysis_request.get("reason")
            or (
                "Initial analysis"
                if revision == 1
                else "Analysis inputs, pipeline, or exposure context changed"
            )
        ),
        input_name=safe_text(item.name),
        versions=manifest,
        organization_snapshot=profiles,
        category=category,
        redacted_text=redacted,
        metadata_json=deepcopy(metadata),
        summary=summary,
        attribution=deepcopy(attributions),
        policy=deepcopy(policy),
        related=deepcopy(related),
    )
    db.add(analysis)
    incident = db.scalar(select(Incident).where(Incident.document_id == document.id))
    if hits or incident:
        if not incident:
            incident = Incident(
                workspace_id=job.workspace_id, document_id=document.id, title=f"Review {document.name}"
            )
            db.add(incident)
        incident.category, incident.priority, incident.status = category, policy["priority"], "open"
        incident.summary, incident.attribution, incident.policy = summary, attributions, policy
        incident.related, incident.updated_at = related, now()
        # Current relationship candidates may grow independently; analysis snapshots remain immutable.
        for link in related:
            peer = db.scalar(
                select(Incident).where(
                    Incident.workspace_id == job.workspace_id, Incident.document_id == link["document_id"]
                )
            )
            if peer:
                peer.related = [r for r in peer.related if r["document_id"] != document.id] + [
                    {**link, "document_id": document.id, "name": document.name, "analysis_revision": revision}
                ]
    db.flush()
    return analysis
