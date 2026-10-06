import json

from app.config import settings
from app.db import SessionLocal
from app.models import Document, Finding, Occurrence
from app.workers.jobs import run_scan
from conftest import upload
from sqlalchemy import func, select


def test_upload_review_export_offline(client, caplog):
    client.post("/api/organizations", json={"name": "Test Company", "domains": ["company.test"]})
    incident, job = upload(client)
    detail = client.get(f"/api/incidents/{incident['id']}").json()
    assert detail["attribution"][0]["assessment"] == "supported"
    assert detail["occurrences"][0]["access_context"] == "supplied"
    assert detail["occurrences"][0]["state"] == "supplied"
    for forbidden in ["synthetic-testing-secret-123456", "person@company.test"]:
        assert forbidden not in json.dumps(detail)
        assert forbidden not in caplog.text
    run = client.post(f"/api/incidents/{incident['id']}/investigations", json={"mode": "offline"}).json()
    run = client.get(f"/api/investigations/{run['id']}").json()
    assert run["status"] == "completed" and run["usage"]["tool_calls"] == 0
    assert "LLM disabled" in str(run["result"])
    for action in ["confirm", "remediate"]:
        assert (
            client.post(
                f"/api/incidents/{incident['id']}/reviews",
                json={"action": action, "reason": "Reviewed synthetic evidence"},
            ).status_code
            == 201
        )
    exported = client.get(f"/api/incidents/{incident['id']}/export")
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    assert exported.json()["report"]["status"] == "remediated"
    assert "synthetic-testing-secret-123456" not in exported.text
    assert len(exported.json()["report"]["reviews"]) == 2


def test_workspace_isolation(client, other_client):
    incident, job = upload(client)
    detail = client.get(f"/api/incidents/{incident['id']}").json()
    run = client.post(f"/api/incidents/{incident['id']}/investigations", json={"mode": "offline"}).json()
    for path in [
        f"/incidents/{incident['id']}",
        f"/incidents/{incident['id']}/export",
        f"/scans/{job['id']}",
        f"/investigations/{run['id']}",
        f"/monitoring/{detail['occurrences'][0]['id']}",
    ]:
        assert other_client.get("/api" + path).status_code == 404
    for path in [
        f"/scans/{job['id']}/cancel",
        f"/scans/{job['id']}/retry",
        f"/sources/{job['source_id']}/scans",
    ]:
        assert other_client.post("/api" + path).status_code == 404
    assert other_client.get("/api/incidents").json()["total"] == 0
    assert (
        other_client.post(
            f"/api/incidents/{incident['id']}/reviews", json={"action": "dismiss", "reason": "Unauthorized"}
        ).status_code
        == 404
    )


def test_csrf_origin_and_login(client):
    assert (
        client.post("/api/organizations", headers={"x-csrf-token": ""}, json={"name": "Example"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/organizations", headers={"origin": "https://attacker.test"}, json={"name": "Example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": "analyst1@example.test", "password": "wrong"}
        ).status_code
        == 401
    )


def test_idempotent_reprocessing(client):
    incident, job = upload(client)
    path = f"/api/sources/{job['source_id']}/scans"
    first = client.post(path, headers={"idempotency-key": "fixed-key"})
    second = client.post(path, headers={"idempotency-key": "fixed-key"})
    assert first.json()["id"] == second.json()["id"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Document)) == 1
        assert db.scalar(select(func.count()).select_from(Occurrence)) == 1
        before = db.scalar(select(func.count()).select_from(Finding))
        run_scan(job["id"])
        assert db.scalar(select(func.count()).select_from(Finding)) == before


def test_benign_does_not_create_incident(client):
    result = client.post(
        "/api/uploads",
        files={"file": ("brochure.txt", b"SYNTHETIC PUBLIC BROCHURE\nTest Company builds robots.")},
    )
    assert client.get(f"/api/scans/{result.json()['id']}").json()["processed"] == 1
    assert client.get("/api/incidents").json()["total"] == 0


def test_ambiguous_name_abstains(client):
    client.post("/api/organizations", json={"name": "Test Company"})
    incident, _ = upload(client, "SYNTHETIC\nTest Company\napi_key=synthetic-testing-secret-123456")
    assert incident["attribution"][0]["assessment"] == "uncertain"


def test_malformed_file(client):
    response = client.post("/api/uploads", files={"file": ("bad.json", b"{SYNTHETIC INVALID JSON")})
    job = client.get(f"/api/scans/{response.json()['id']}").json()
    assert job["status"] == "partial" and job["processed"] == 0 and job["errors"]
    assert "SYNTHETIC INVALID JSON" not in str(job)


def test_path_traversal_and_limits(client, monkeypatch):
    upload(client, name="../../secret.env")
    assert client.get("/api/sources").json()["items"][0]["config"]["filename"] == "secret.env"
    monkeypatch.setattr(settings(), "max_file_bytes", 10)
    assert client.post("/api/uploads", files={"file": ("large.txt", b"x" * 11)}).status_code == 413
    assert client.post("/api/uploads", files={"file": ("archive.zip", b"fake")}).status_code == 415


def test_cancelled_job_is_not_processed(client, monkeypatch):
    import app.workers.jobs as jobs

    monkeypatch.setattr(jobs, "enqueue", lambda *args: None)
    job = client.post("/api/uploads", files={"file": ("test.txt", b"SYNTHETIC")}).json()
    assert client.post(f"/api/scans/{job['id']}/cancel").json()["status"] == "cancelled"
    run_scan(job["id"])
    assert client.get(f"/api/scans/{job['id']}").json()["processed"] == 0


def test_raw_expiry_preserves_evidence(client):
    incident, job = upload(client)
    (settings().data_dir / "uploads" / job["source_id"]).unlink()
    result = client.post(f"/api/sources/{job['source_id']}/scans").json()
    assert client.get(f"/api/scans/{result['id']}").json()["status"] == "failed"
    assert client.get(f"/api/incidents/{incident['id']}/export").status_code == 200


def test_live_gate_placeholder_and_override(client):
    incident, _ = upload(client, "SYNTHETIC\napi_key=changeme", "README.md")
    assert incident["status"] == "open"
    detail = client.get(f"/api/incidents/{incident['id']}").json()
    assert any(f["placeholder"] for f in detail["findings"])
    assert (
        client.post(f"/api/incidents/{incident['id']}/investigations", json={"mode": "live"}).status_code
        == 409
    )
    path = f"/api/incidents/{incident['id']}/reviews"
    assert (
        client.post(path, json={"action": "change_priority", "reason": "Owner confirmation"}).status_code
        == 422
    )
    assert (
        client.post(
            path, json={"action": "change_priority", "reason": "Owner confirmation", "priority": "high"}
        ).status_code
        == 201
    )
    assert client.get("/api/incidents?priority=high").json()["total"] == 1
    assert client.get("/api/incidents?limit=1&offset=1").json()["items"] == []


def test_read_only_workspace_can_logout(client, monkeypatch):
    monkeypatch.setattr(settings(), "public_read_only", True)
    assert client.post("/api/organizations", json={"name": "Blocked change"}).status_code == 403
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_active_filter_includes_confirmed(client):
    incident, _ = upload(client)
    client.post(
        f"/api/incidents/{incident['id']}/reviews",
        json={"action": "confirm", "reason": "Synthetic reviewed evidence"},
    )
    assert client.get("/api/incidents?status=active").json()["total"] == 1
