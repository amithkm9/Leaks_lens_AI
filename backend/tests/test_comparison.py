import json

import pytest
from app.analysis import get_analysis
from app.comparison import text_changes
from app.db import SessionLocal
from app.models import Document, Finding
from conftest import upload
from sqlalchemy import select


def compare(client, incident, earlier=1, later=2):
    return client.get(
        f"/api/incidents/{incident['id']}/comparison", params={"from_revision": earlier, "to_revision": later}
    )


def refresh(client, incident, source):
    response = client.post(
        f"/api/incidents/{incident['id']}/reanalyses",
        json={
            "source_id": source,
            "expected_analysis_revision": 1,
            "reason": "Compare current inputs",
        },
    )
    assert response.status_code == 202, response.text


def test_compare_profile_refresh_preserves_original_evidence_and_hides_fingerprints(client):
    incident, job = upload(client)
    client.post("/api/organizations", json={"name": "Example Organization", "domains": ["company.test"]})
    refresh(client, incident, job["source_id"])
    response = compare(client, incident)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["changed_inputs"] == ["Organization profiles"]
    assert result["from_analysis"]["revision"] == 1 and result["to_analysis"]["revision"] == 2
    assert result["findings"]["added_count"] == result["findings"]["removed_count"] == 0
    assert result["findings"]["unchanged_count"] > 0
    assert result["organizations"]["before"] == []
    assert result["organizations"]["after"][0]["name"] == "Example Organization"
    assert result["text"] == {"changed": False, "lines": [], "complete": True}
    assert "synthetic-testing-secret-123456" not in response.text
    with SessionLocal() as db:
        fingerprint = db.scalar(select(Finding.fingerprint))
        assert fingerprint not in response.text


def test_compare_counts_repeated_values_and_links_each_changed_finding(client):
    incident, job = upload(client)
    refresh(client, incident, job["source_id"])
    with SessionLocal() as db:
        old = db.scalar(select(Finding).where(Finding.analysis_revision == 1))
        db.add(
            Finding(
                workspace_id=old.workspace_id,
                document_id=old.document_id,
                analysis_revision=2,
                evidence_id=next(
                    f.evidence_id
                    for f in db.scalars(select(Finding).where(Finding.analysis_revision == 2))
                    if f.fingerprint == old.fingerprint
                ),
                finding_type=old.finding_type,
                detector=old.detector,
                detector_version=old.detector_version,
                fingerprint=old.fingerprint,
                placeholder=False,
            )
        )
        # Removing a different match changes counts, without exposing keyed secret identities.
        other = db.scalar(
            select(Finding).where(Finding.analysis_revision == 2, Finding.fingerprint != old.fingerprint)
        )
        removed = other.evidence_id
        db.delete(other)
        db.commit()
    result = compare(client, incident).json()["findings"]
    assert result["added_count"] == 1 and result["removed_count"] == 1
    assert result["added"][0]["analysis_revision"] == 2
    assert result["removed"][0]["analysis_revision"] == 1
    assert result["removed"][0]["evidence_id"] != removed
    assert result["unchanged_count"] >= 1


@pytest.mark.parametrize("restricted_revision", [1, 2])
def test_comparison_cannot_bypass_historical_restrictions(client, other_client, restricted_revision):
    incident, job = upload(client)
    refresh(client, incident, job["source_id"])
    assert compare(other_client, incident).status_code == 404
    assert compare(client, incident, 1, 9).status_code == 404
    assert compare(client, incident, 2, 1).status_code == 422
    assert compare(client, incident, 1, 1).status_code == 422
    with SessionLocal() as db:
        analysis = get_analysis(db, db.get(Document, incident["document_id"]), restricted_revision)
        analysis.redaction_status = "restricted"
        analysis.redacted_text = "restricted-comparison-canary"
        db.commit()
    response = compare(client, incident)
    assert response.status_code == 409 and "restricted-comparison-canary" not in response.text


def test_diff_is_bounded_and_reports_changes_outside_the_preview():
    before = "same context\n" * 10000 + "before\n"
    after = "same context\n" * 10000 + "after\n"
    result = text_changes(before, after)
    assert result["changed"] and not result["complete"]
    assert len(result["lines"]) <= 400
    assert len(json.dumps(result)) < 30000
    small = text_changes("alpha\nbefore\n", "alpha\nafter\n")
    assert small["complete"] and "-before" in small["lines"] and "+after" in small["lines"]
    huge_line = text_changes("a" * 30000, "b" * 30000)
    assert not huge_line["complete"] and sum(map(len, huge_line["lines"])) <= 24000
