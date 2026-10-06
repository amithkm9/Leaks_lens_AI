"""Bounded, read-only comparisons of two analyses of the same original content."""

from collections import defaultdict
from difflib import unified_diff
from itertools import islice

from fastapi import HTTPException
from sqlalchemy import select

from app.analysis import analysis_metadata, get_analysis, organization_snapshot, restricted
from app.detectors import sanitize
from app.models import Document, Evidence, Finding
from app.security import scoped

TEXT_CHARS = 24000
TEXT_LINES = 400
FINDING_LIMIT = 100


def text_changes(before, after):
    if before == after:
        return {"changed": False, "lines": [], "complete": True}
    left = before[:TEXT_CHARS].splitlines(keepends=True)[:TEXT_LINES]
    right = after[:TEXT_CHARS].splitlines(keepends=True)[:TEXT_LINES]
    complete = "".join(left) == before and "".join(right) == after
    # Bound both SequenceMatcher inputs and returned output; repeated-line documents
    # must not cause unbounded CPU work or enormous browser reports.
    output = list(
        islice(
            unified_diff(left, right, fromfile="Earlier analysis", tofile="Later analysis", n=2),
            TEXT_LINES + 1,
        )
    )
    if len(output) > TEXT_LINES:
        complete = False
    rendered, chars = [], 0
    for line in output[:TEXT_LINES]:
        remaining = TEXT_CHARS - chars
        if remaining <= 0:
            complete = False
            break
        rendered.append(line[:remaining].rstrip("\r\n"))
        chars += len(line)
        if len(line) > remaining:
            complete = False
    return {"changed": True, "lines": rendered, "complete": complete}


def finding_changes(db, document, before, after):
    buckets = {before: defaultdict(list), after: defaultdict(list)}
    rows = db.execute(
        select(Finding, Evidence.location)
        .join(Evidence, Evidence.id == Finding.evidence_id)
        .where(
            Finding.document_id == document.id,
            Finding.workspace_id == document.workspace_id,
            Finding.analysis_revision.in_([before, after]),
            Evidence.workspace_id == document.workspace_id,
            Evidence.analysis_revision == Finding.analysis_revision,
        )
        .order_by(Finding.created_at, Finding.id)
    ).all()
    for finding, location in rows:
        buckets[finding.analysis_revision][(finding.finding_type, finding.fingerprint)].append(
            {
                "id": finding.id,
                "evidence_id": finding.evidence_id,
                "finding_type": finding.finding_type,
                "detector": finding.detector,
                "line": location.get("line"),
                "analysis_revision": finding.analysis_revision,
            }
        )
    added, removed, unchanged = [], [], 0
    for key in sorted(set(buckets[before]) | set(buckets[after])):
        left, right = buckets[before][key], buckets[after][key]
        shared = min(len(left), len(right))
        unchanged += shared
        removed.extend(left[shared:])
        added.extend(right[shared:])
    return {
        "added_count": len(added),
        "removed_count": len(removed),
        "unchanged_count": unchanged,
        "added": added[:FINDING_LIMIT],
        "removed": removed[:FINDING_LIMIT],
        "complete": len(added) <= FINDING_LIMIT and len(removed) <= FINDING_LIMIT,
    }


def compare_analyses(db, incident, from_revision, to_revision):
    if from_revision >= to_revision:
        raise HTTPException(422, "Choose an earlier revision to compare with the selected analysis")
    document = scoped(db, Document, incident.document_id, incident.workspace_id)
    before = get_analysis(db, document, from_revision)
    after = get_analysis(db, document, to_revision)
    if before is None or after is None:
        raise HTTPException(404, "Analysis revision not found")
    if restricted(before) or restricted(after):
        raise HTTPException(
            409,
            "Restricted analyses cannot be compared. Reanalyze original bytes to create an available revision.",
        )
    profiles = organization_snapshot(db, incident.workspace_id)
    inputs = {
        "organization_profiles": "Organization profiles",
        "attribution": "Attribution rules",
        "policy": "Priority policy",
        "format": "Input format",
        "access_context": "Exposure context",
        "redaction": "Redaction pipeline",
    }
    return sanitize(
        {
            "document_id": document.id,
            "from_analysis": analysis_metadata(before, document.analysis_revision, profiles),
            "to_analysis": analysis_metadata(after, document.analysis_revision, profiles),
            "changed_inputs": [
                label for key, label in inputs.items() if before.versions.get(key) != after.versions.get(key)
            ],
            "category": {"before": before.category, "after": after.category},
            "policy_priority": {
                "before": before.policy.get("priority", "low"),
                "after": after.policy.get("priority", "low"),
            },
            "organizations": {
                "before": [
                    {"id": a["organization_id"], "name": a["name"], "assessment": a["assessment"]}
                    for a in before.attribution
                ],
                "after": [
                    {"id": a["organization_id"], "name": a["name"], "assessment": a["assessment"]}
                    for a in after.attribution
                ],
            },
            "findings": finding_changes(db, document, before.revision, after.revision),
            "text": text_changes(before.redacted_text, after.redacted_text),
            "note": "Both analyses use the same original content. Findings are matched by type and keyed value identity, including repeated occurrences. Changes in analysis do not establish removal, revocation, or remediation.",
        }
    )
