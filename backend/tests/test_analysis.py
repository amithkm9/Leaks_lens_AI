"""Revision boundaries, original-byte reanalysis, and historical disclosure guards."""

import json
import sys
from pathlib import Path
import pytest
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from sqlalchemy import select, func
from app import detectors
from app.analysis import get_analysis, redaction_manifest
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Document,
    DocumentAnalysis,
    Evidence,
    Incident,
    Investigation,
    Occurrence,
    ScanJob,
    ToolCall,
)
from conftest import upload


def detail(client, incident, revision=None):
    response = client.get(
        f"/api/incidents/{incident['id']}", params={"analysis_revision": revision} if revision else {}
    )
    assert response.status_code == 200, response.text
    return response.json()


def reanalyze(client, incident, source, revision=1):
    return client.post(
        f"/api/incidents/{incident['id']}/reanalyses",
        json={
            "source_id": source,
            "expected_analysis_revision": revision,
            "reason": "Refresh original evidence",
        },
    )


def test_refresh_preserves_history_and_rejects_stale_decisions(client):
    incident, job = upload(client)
    original = detail(client, incident)
    review = client.post(
        f"/api/incidents/{incident['id']}/reviews",
        json={
            "action": "confirm",
            "reason": "Reviewed original evidence",
            "analysis_revision": 1,
        },
    ).json()
    run = client.post(
        f"/api/incidents/{incident['id']}/investigations", json={"mode": "offline", "analysis_revision": 1}
    ).json()
    # Compatible observations reuse evidence and retain the analyst's decision.
    client.post(f"/api/sources/{job['source_id']}/scans")
    assert detail(client, incident)["status"] == "confirmed"
    assert detail(client, incident)["evidence"] == original["evidence"]
    assert reanalyze(client, incident, job["source_id"]).status_code == 202
    current, historical = detail(client, incident), detail(client, incident, 1)
    assert current["analysis_revision"] == 2 and current["status"] == "open"
    assert current["reviews"] == [] and current["investigations"] == []
    assert current["document"]["redacted_text"] == original["document"]["redacted_text"]
    assert {e["id"] for e in current["evidence"]}.isdisjoint(e["id"] for e in historical["evidence"])
    assert historical["evidence"] == original["evidence"]
    assert historical["status"] == "confirmed" and historical["reviews"][0]["id"] == review["id"]
    assert historical["investigations"][0]["id"] == run["id"]
    for endpoint, payload in [
        ("reviews", {"action": "dismiss", "reason": "Old screen", "analysis_revision": 1}),
        ("investigations", {"mode": "offline", "analysis_revision": 1}),
    ]:
        assert client.post(f"/api/incidents/{incident['id']}/{endpoint}", json=payload).status_code == 409
    assert reanalyze(client, incident, job["source_id"]).status_code == 409
    report = client.get(f"/api/incidents/{incident['id']}/export?analysis_revision=1").json()
    assert report["schema_version"] == "2"
    assert report["report"]["analysis_revision"] == 1 and report["report"]["status"] == "confirmed"
    assert "synthetic-testing-secret-123456" not in json.dumps(report)


def test_profiles_make_results_stale_and_normal_scan_reanalyzes(client):
    incident, job = upload(client)
    assert (
        client.post(
            "/api/organizations", json={"name": "Synthetic Organization", "domains": ["company.test"]}
        ).status_code
        == 201
    )
    old = detail(client, incident)
    assert old["analysis"]["freshness"] == "stale" and not old["analysis"]["restricted"]
    client.post(f"/api/sources/{job['source_id']}/scans")
    current = detail(client, incident)
    assert current["analysis_revision"] == 2
    assert current["analysis"]["freshness"] == "current"
    assert current["attribution"] and not detail(client, incident, 1)["attribution"]
    with SessionLocal() as db:
        revisions = db.scalars(select(DocumentAnalysis).order_by(DocumentAnalysis.revision)).all()
        assert revisions[0].organization_snapshot == []
        assert revisions[1].organization_snapshot[0]["domains"] == ["company.test"]


def test_detector_change_quarantines_old_data_on_all_channels(client, monkeypatch):
    incident, job = upload(client)
    run = client.post(f"/api/incidents/{incident['id']}/investigations", json={"mode": "offline"}).json()
    marker = "historical-sensitive-canary"
    with SessionLocal() as db:
        doc = db.get(Document, incident["document_id"])
        analysis = get_analysis(db, doc)
        analysis.redacted_text = marker
        analysis.summary = marker
        doc.redacted_text = marker
        db.get(Incident, incident["id"]).summary = marker
        db.scalar(select(Evidence)).excerpt = marker
        saved_run = db.get(Investigation, run["id"])
        saved_run.result = {"summary": marker}
        db.add(
            ToolCall(
                workspace_id=doc.workspace_id,
                investigation_id=run["id"],
                name="get_redacted_content",
                arguments={},
                result={"text": marker},
                duration_ms=1,
                success=True,
            )
        )
        db.commit()
    monkeypatch.setattr(detectors, "CUSTOM_VERSION", "future-test-version")
    for endpoint in [
        "/api/incidents",
        f"/api/incidents/{incident['id']}",
        f"/api/investigations/{run['id']}",
    ]:
        response = client.get(endpoint)
        assert response.status_code == 200 and marker not in response.text
    assert client.get(f"/api/incidents/{incident['id']}/export").status_code == 409
    assert (
        client.post(f"/api/incidents/{incident['id']}/investigations", json={"mode": "offline"}).status_code
        == 409
    )
    assert reanalyze(client, incident, job["source_id"]).status_code == 202
    assert detail(client, incident)["analysis"]["restricted"] is False
    assert detail(client, incident, 1)["analysis"]["restricted"] is True
    assert client.get(f"/api/incidents/{incident['id']}/export?analysis_revision=1").status_code == 409
    with SessionLocal() as db:
        assert get_analysis(db, db.get(Document, incident["document_id"]), 1).redacted_text == marker


def test_expired_changed_and_failed_inputs_preserve_current_analysis(client, monkeypatch):
    incident, job = upload(client)
    original = detail(client, incident)
    path = settings().data_dir / "uploads" / job["source_id"]
    content = path.read_bytes()
    path.unlink()
    result = reanalyze(client, incident, job["source_id"])
    assert result.status_code == 409 and "upload the original" in result.text
    path.write_text("Replacement content")
    result = reanalyze(client, incident, job["source_id"])
    failed = client.get(f"/api/scans/{result.json()['id']}").json()
    assert failed["status"] == "failed" and "Original bytes" in failed["errors"][0]
    path.write_bytes(content)
    import app.workers.analysis as worker

    original_priority = worker.priority

    def fail_priority(*args):
        raise ValueError("Synthetic policy failure after evidence writes")

    monkeypatch.setattr(worker, "priority", fail_priority)
    result = reanalyze(client, incident, job["source_id"])
    partial = client.get(f"/api/scans/{result.json()['id']}").json()
    assert partial["status"] == "partial" and partial["processed"] == 0
    assert detail(client, incident)["evidence"] == original["evidence"]
    assert detail(client, incident)["analysis_revision"] == 1
    monkeypatch.setattr(worker, "priority", original_priority)
    client.post(f"/api/scans/{partial['id']}/retry")
    assert detail(client, incident)["analysis_revision"] == 2
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 1


def test_source_refresh_includes_no_finding_analyses_and_can_create_incident(client, monkeypatch):
    result = client.post(
        "/api/uploads", files={"file": ("benign.txt", b"SYNTHETIC internal_code=ABC123")}
    ).json()
    source = result["source_id"]
    assert client.get("/api/incidents").json()["total"] == 0
    with SessionLocal() as db:
        analysis = db.scalar(select(DocumentAnalysis))
        assert analysis.revision == 1 and analysis.metadata_json["finding_count"] == 0
    import app.workers.analysis as worker

    base = worker.detect

    def upgraded(raw):
        # Controlled new rule matches original content; masked-text analysis would be incorrect.
        assert raw == "SYNTHETIC internal_code=ABC123"
        _, hits, warnings = base("api_key=ABC123")
        return "SYNTHETIC internal_code=██████", [{**h, "start": 24, "end": 30} for h in hits], warnings

    monkeypatch.setattr(worker, "detect", upgraded)
    result = client.post(
        f"/api/sources/{source}/reanalyses", json={"expected_revision": 1, "reason": "New rule"}
    )
    assert result.status_code == 202
    cases = client.get("/api/incidents").json()["items"]
    assert len(cases) == 1 and detail(client, cases[0])["analysis_revision"] == 2
    assert detail(client, cases[0], 1)["findings"] == []


def test_reanalysis_scope_revision_archive_and_active_job_guards(client, other_client, monkeypatch):
    incident, job = upload(client)
    foreign, foreign_job = upload(other_client)
    assert reanalyze(other_client, incident, job["source_id"]).status_code == 404
    assert reanalyze(client, incident, foreign_job["source_id"]).status_code == 404
    source = job["source_id"]
    assert (
        client.post(
            f"/api/sources/{source}/reanalyses", json={"expected_revision": 999, "reason": "Stale source"}
        ).status_code
        == 409
    )
    import app.api.main as api

    monkeypatch.setattr(api, "enqueue", lambda *args: None)
    response = reanalyze(client, incident, source)
    assert response.status_code == 202
    assert reanalyze(client, incident, source).status_code == 409
    client.post(f"/api/scans/{response.json()['id']}/cancel")
    client.post(f"/api/sources/{source}/archive", json={"expected_revision": 1, "archived": True})
    assert reanalyze(client, incident, source).status_code == 409
    assert client.get(f"/api/incidents/{incident['id']}?analysis_revision=9").status_code == 404
    assert client.get(f"/api/incidents/{incident['id']}?analysis_revision=0").status_code == 422


async def test_real_mcp_pins_original_evidence_after_reanalysis(client):
    incident, job = upload(client)
    original = detail(client, incident)
    run = client.post(f"/api/incidents/{incident['id']}/investigations", json={"mode": "offline"}).json()
    assert reanalyze(client, incident, job["source_id"]).status_code == 202
    with SessionLocal() as db:
        saved = db.get(Investigation, run["id"])
        workspace, scope = saved.workspace_id, saved.scope_snapshot
    transport = StdioTransport(
        command=sys.executable,
        args=["-m", "app.mcp.server"],
        cwd=str(Path(__file__).resolve().parents[1]),
        env={
            "DATABASE_URL": settings().database_url,
            "FINGERPRINT_KEY": settings().fingerprint_key,
            "LEAKLENS_MCP_WORKSPACE": workspace,
            "LEAKLENS_MCP_CASE": incident["id"],
            "LEAKLENS_MCP_SCOPE": json.dumps(scope),
            "LEAKLENS_MCP_REDACTION": json.dumps(redaction_manifest()),
        },
        keep_alive=False,
    )
    async with Client(transport) as mcp:
        result = await mcp.call_tool("get_redacted_content", {"document_id": incident["document_id"]})
        assert result.data["data"]["analysis_revision"] == 1
        assert set(result.data["evidence_ids"]) == {e["id"] for e in original["evidence"]}
        with SessionLocal() as db:
            analysis = get_analysis(db, db.get(Document, incident["document_id"]), 1)
            analysis.redaction_status = "restricted"
            db.commit()
        with pytest.raises(Exception):
            await mcp.call_tool("get_redacted_content", {"document_id": incident["document_id"]})


def test_targeted_reanalysis_does_not_mark_unrelated_occurrences_absent(client, monkeypatch, tmp_path):
    first, job = upload(client)
    second, _ = upload(client, "SYNTHETIC\napi_key=synthetic-other-secret-789012")
    from app.models import Source
    from app.connectors import Collection, Item
    import app.workers.jobs as worker

    with SessionLocal() as db:
        source = db.get(Source, job["source_id"])
        source.kind = "git"
        other = db.scalar(select(Occurrence).where(Occurrence.document_id == second["document_id"]))
        other.source_id, other.state = source.id, "observed"
        other_id = other.id
        db.commit()
    path = settings().data_dir / "uploads" / job["source_id"]
    monkeypatch.setattr(
        worker.git, "collect", lambda *args: Collection(items=[Item(path, "sample.env", "sample.env")])
    )
    assert reanalyze(client, first, job["source_id"]).status_code == 202
    with SessionLocal() as db:
        assert db.get(Occurrence, other_id).state == "observed"
        assert db.get(Document, second["document_id"]).analysis_revision == 1
        assert db.scalar(select(func.count()).select_from(ScanJob).where(ScanJob.status == "failed")) == 0


def test_no_findings_revision_needs_review_and_queued_assessment_keeps_original(client, monkeypatch):
    incident, job = upload(client)
    original = detail(client, incident)
    client.post(
        f"/api/incidents/{incident['id']}/reviews",
        json={"action": "remediate", "reason": "Original owner review"},
    )
    import app.api.main as api
    import app.workers.analysis as worker
    from app.workers.jobs import run_scan
    from app.agent.runner import run_investigation

    monkeypatch.setattr(api, "enqueue", lambda *args: None)
    queued = client.post(f"/api/incidents/{incident['id']}/investigations", json={"mode": "offline"}).json()
    monkeypatch.setattr(worker, "detect", lambda raw: ("[Controlled negative result]", [], []))
    response = reanalyze(client, incident, job["source_id"])
    run_scan(response.json()["id"])
    current = detail(client, incident)
    assert current["analysis_revision"] == 2 and current["findings"] == []
    assert current["status"] == "open" and current["reviews"] == []
    assert detail(client, incident, 1)["status"] == "remediated"
    run_investigation(queued["id"])
    result = client.get(f"/api/investigations/{queued['id']}").json()
    assert result["status"] == "completed" and result["analysis_revision"] == 1
    assert result["result"]["summary"] == original["summary"]
    assert set(result["result"]["supporting_evidence_ids"]) == {e["id"] for e in original["evidence"]}
    assert client.post(f"/api/scans/{response.json()['id']}/retry").status_code == 409


def test_repeated_bytes_within_forced_source_scan_create_one_revision(client, monkeypatch):
    incident, job = upload(client)
    from app.models import Source
    from app.connectors import Collection, Item
    import app.workers.jobs as worker

    with SessionLocal() as db:
        db.get(Source, job["source_id"]).kind = "git"
        db.commit()
    path = settings().data_dir / "uploads" / job["source_id"]
    monkeypatch.setattr(
        worker.git,
        "collect",
        lambda *args: Collection(
            items=[
                Item(path, "sample.env", "one.env"),
                Item(path, "sample.env", "two.env"),
            ]
        ),
    )
    response = client.post(
        f"/api/sources/{job['source_id']}/reanalyses",
        json={"expected_revision": 1, "reason": "Explicit source refresh"},
    )
    saved = client.get(f"/api/scans/{response.json()['id']}").json()
    assert saved["processed"] == 2 and saved["errors"] == []
    assert detail(client, incident)["analysis_revision"] == 2
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DocumentAnalysis)) == 2
