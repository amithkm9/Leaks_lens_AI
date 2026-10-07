from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import DocumentAnalysis, RemediationEvent, RemediationTask
from conftest import upload
from sqlalchemy import select


def create(client, incident, **values):
    response = client.post(
        f"/api/incidents/{incident['id']}/remediation-tasks",
        json={"title": "Rotate exposed credential", "analysis_revision": 1, **values},
    )
    assert response.status_code == 201, response.text
    return response.json()


def edit(client, task, **values):
    fields = {
        key: task[key]
        for key in (
            "title",
            "analysis_revision",
            "owner_id",
            "due_date",
            "evidence_ids",
            "status",
            "action_taken",
            "verification_method",
            "verification_notes",
        )
    }
    return client.put(
        f"/api/remediation-tasks/{task['id']}",
        json={
            **fields,
            "expected_revision": task["revision"],
            "reason": "Analyst follow-up",
            **values,
        },
    )


def test_task_completion_verification_audit_and_reopening(client):
    incident, _ = upload(client)
    member = client.get("/api/workspace/members").json()["items"][0]
    assert set(member) == {"id", "email"}
    task = create(client, incident, owner_id=member["id"], due_date="2026-01-01")
    assert task["overdue"] and task["owner_email"] == member["email"]
    assert edit(client, task, status="completed").status_code == 422
    task = edit(client, task, status="completed", action_taken="Replaced the test credential").json()
    assert task["verified_at"] is None and not task["overdue"]
    assert client.get("/api/overview").json()["remediation"]["awaiting_verification"] == 1
    assert edit(client, task, verification_method="credential_rotation").status_code == 422
    task = edit(
        client,
        task,
        verification_method="credential_rotation",
        verification_notes="Operator confirmed revocation in the credential console",
    ).json()
    assert task["verified_by"] == member["id"] and task["verified_at"]
    original_verification = task["verified_at"]
    task = edit(client, task, due_date="2026-02-01").json()
    assert task["verified_at"] == original_verification
    task = edit(client, task, status="in_progress", verification_method=None, verification_notes="").json()
    assert task["verified_at"] is None and task["verified_by"] is None
    history = client.get(f"/api/remediation-tasks/{task['id']}/history").json()
    assert history["total"] == 5
    assert history["items"][0]["revision"] == 5
    assert history["items"][-1]["snapshot"]["status"] == "open"
    assert history["items"][2]["snapshot"]["verified_at"] == original_verification
    assert all(event["actor_email"] == member["email"] for event in history["items"])
    report = client.get(f"/api/incidents/{incident['id']}/export").json()["report"]
    assert report["status"] == "open" and report["reviews"] == []
    assert report["remediation"]["items"][0]["id"] == task["id"]


def test_task_scope_owner_evidence_and_security_guards(client, other_client, monkeypatch):
    incident, _ = upload(client)
    other, _ = upload(other_client)
    foreign_member = other_client.get("/api/workspace/members").json()["items"][0]
    foreign_evidence = other_client.get(f"/api/incidents/{other['id']}").json()["evidence"][0]["id"]
    path = f"/api/incidents/{incident['id']}/remediation-tasks"
    payload = {"title": "Scoped follow-up", "analysis_revision": 1}
    assert other_client.post(path, json=payload).status_code == 404
    assert client.post(path, json={**payload, "owner_id": foreign_member["id"]}).status_code == 404
    assert client.post(path, json={**payload, "evidence_ids": [foreign_evidence]}).status_code == 422
    assert client.post(path, json=payload, headers={"x-csrf-token": ""}).status_code == 403
    task = create(client, incident)
    assert edit(other_client, task).status_code == 404
    assert other_client.get(f"/api/remediation-tasks/{task['id']}/history").status_code == 404
    assert other_client.get(f"/api/remediation-tasks?incident_id={incident['id']}").status_code == 404
    assert other_client.get("/api/remediation-tasks?state=all").json()["total"] == 0
    assert other_client.get("/api/overview").json()["remediation"]["active"] == 0
    from app.config import settings

    monkeypatch.setattr(settings(), "public_read_only", True)
    assert client.post(path, json=payload).status_code == 403
    assert edit(client, task).status_code == 403


def test_stale_edits_and_validation_do_not_append_events(client):
    incident, _ = upload(client)
    task = create(client, incident)
    assert edit(client, task, status="blocked").status_code == 200
    assert edit(client, task, title="Lost update").status_code == 409
    current = client.get("/api/remediation-tasks").json()["items"][0]
    for changes in (
        {"owner_id": "   "},
        {"reason": "   "},
        {"due_date": "not-a-date"},
        {"status": "invented"},
        {"title": "   "},
        {"verification_notes": "No method"},
        {"evidence_ids": ["foreign"]},
    ):
        assert edit(client, current, **changes).status_code == 422
    assert edit(client, current, analysis_revision=2).status_code == 409
    assert client.get(f"/api/remediation-tasks/{task['id']}/history").json()["total"] == 2


def test_redaction_and_restricted_analysis_cover_every_task_read(client):
    incident, _ = upload(client)
    secret = "synthetic-remediation-secret-123456"
    task = create(client, incident, title=f"Rotate api_key={secret}")
    response = edit(client, task, action_taken=f"api_key={secret}", reason=f"api_key={secret}")
    assert response.status_code == 200
    paths = [
        "/api/remediation-tasks?state=all",
        "/api/overview",
        f"/api/remediation-tasks/{task['id']}/history",
        f"/api/incidents/{incident['id']}/export",
    ]
    for path in paths:
        assert secret not in client.get(path).text
    with SessionLocal() as db:
        row = db.scalar(
            select(DocumentAnalysis).where(DocumentAnalysis.document_id == incident["document_id"])
        )
        row.redaction_status = "restricted"
        db.get(RemediationTask, task["id"]).title = "LEGACY_UNSAFE_TEXT"
        saved = db.scalar(select(RemediationEvent).where(RemediationEvent.task_id == task["id"]))
        saved.reason = "LEGACY_UNSAFE_TEXT"
        saved.snapshot = {"title": "LEGACY_UNSAFE_TEXT"}
        db.commit()
    for path in paths[:-1] + [f"/api/incidents/{incident['id']}"]:
        response = client.get(path)
        assert response.status_code == 200 and "LEGACY_UNSAFE_TEXT" not in response.text
    assert client.get(paths[-1]).status_code == 409
    restricted_task = client.get("/api/remediation-tasks?state=all").json()["items"][0]
    assert edit(client, restricted_task).status_code == 409


def test_tasks_preserve_original_analysis_and_allow_historical_follow_up(client):
    incident, job = upload(client)
    path = f"/api/incidents/{incident['id']}"
    evidence = client.get(path).json()["evidence"][0]["id"]
    task = create(client, incident, evidence_ids=[evidence])
    response = client.post(
        path + "/reanalyses",
        json={
            "source_id": job["source_id"],
            "expected_analysis_revision": 1,
            "reason": "New analysis inputs",
        },
    )
    assert response.status_code == 202
    assert client.get(path).json()["remediation"]["total"] == 0
    assert client.get(path + "?analysis_revision=1").json()["remediation"]["total"] == 1
    assert (
        client.post(
            path + "/remediation-tasks", json={"analysis_revision": 1, "title": "Stale form"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            path + "/remediation-tasks",
            json={"analysis_revision": 2, "title": "Wrong evidence", "evidence_ids": [evidence]},
        ).status_code
        == 422
    )
    updated = edit(client, task, status="completed", action_taken="Rotated the credential from revision one")
    assert updated.status_code == 200
    assert updated.json()["analysis_revision"] == 1 and updated.json()["current_analysis_revision"] == 2
    assert client.get(path).json()["status"] == "open"


def test_queue_counts_due_boundary_sorting_and_pagination(client):
    incident, _ = upload(client)
    today = datetime.now(timezone.utc).date()
    member = client.get("/api/workspace/members").json()["items"][0]
    later = create(client, incident, due_date=(today + timedelta(days=1)).isoformat())
    create(client, incident, due_date=today.isoformat())
    overdue = create(
        client, incident, due_date=(today - timedelta(days=1)).isoformat(), owner_id=member["id"]
    )
    create(client, incident)
    completed = create(client, incident, due_date="2020-01-01")
    edit(client, completed, status="completed", action_taken="Credential removed from fixture")
    summary = client.get("/api/overview").json()["remediation"]
    assert (summary["active"], summary["overdue"], summary["awaiting_verification"]) == (4, 1, 1)
    assert summary["next_tasks"][0]["id"] == overdue["id"]
    assert client.get("/api/remediation-tasks?state=overdue").json()["total"] == 1
    assert client.get("/api/remediation-tasks?owner=me").json()["total"] == 1
    assert client.get("/api/remediation-tasks?owner=unassigned").json()["total"] == 3
    first = client.get("/api/remediation-tasks?limit=2").json()
    second = client.get("/api/remediation-tasks?limit=2&offset=2").json()
    assert first["total"] == second["total"] == 4
    assert second["items"][0]["id"] == later["id"]
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    assert client.get("/api/remediation-tasks?state=typo").status_code == 422
