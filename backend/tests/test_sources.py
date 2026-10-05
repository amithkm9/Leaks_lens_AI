import pytest
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Source, User
from app.workers.jobs import run_scan
from conftest import upload


@pytest.fixture
def remote_source(client, monkeypatch):
    monkeypatch.setattr("app.api.main.validate_url", lambda *args: None)
    payload = {
        "name": "Synthetic documents",
        "kind": "http",
        "authorized": True,
        "access_context": "authorized_private",
        "config": {
            "url": "https://files.example.test/approved/file.txt",
            "allowed_hosts": ["files.example.test"],
            "path_prefixes": ["/approved"],
            "max_depth": 0,
            "max_documents": 20,
        },
    }
    response = client.post("/api/sources", json=payload)
    assert response.status_code == 201, response.text
    return response.json(), payload


def test_source_edit_history_and_stale_revision(client, remote_source):
    source, payload = remote_source
    path = f"/api/sources/{source['id']}"
    updated = client.put(path, json={**payload, "name": "Renamed documents", "expected_revision": 1})
    assert updated.status_code == 200, updated.text
    assert updated.json()["revision"] == 2
    assert updated.json()["config"]["max_depth"] == 0
    assert client.put(path, json={**payload, "expected_revision": 1}).status_code == 409
    history = client.get(path + "/history").json()
    assert history["total"] == 2
    assert [e["action"] for e in history["items"]] == ["updated", "created"]
    assert history["items"][1]["snapshot"]["name"] == payload["name"]
    assert history["items"][0]["user_id"]
    assert client.put(path, json={**payload, "authorized": False, "expected_revision": 2}).status_code == 422
    assert (
        client.put(
            path,
            json={
                **payload,
                "config": {**payload["config"], "url": "https://files.example.test/other.txt"},
                "expected_revision": 2,
            },
        ).status_code
        == 409
    )


def test_archive_restore_preserves_evidence_and_blocks_collection(client):
    incident, job = upload(client)
    path = f"/api/sources/{job['source_id']}"
    archived = client.post(path + "/archive", json={"archived": True, "expected_revision": 1})
    assert archived.status_code == 200
    assert archived.json()["archived_at"]
    assert client.get("/api/sources").json()["total"] == 0
    assert client.get("/api/sources?state=archived").json()["total"] == 1
    assert client.get("/api/overview").json()["sources"] == 0
    assert client.get(f"/api/incidents/{incident['id']}/export").status_code == 200
    assert client.post(path + "/check").status_code == 409
    assert client.post(path + "/scans").status_code == 409
    assert client.post(f"/api/scans/{job['id']}/retry").status_code == 409
    assert client.post(path + "/archive", json={"archived": False, "expected_revision": 1}).status_code == 409
    restored = client.post(path + "/archive", json={"archived": False, "expected_revision": 2})
    assert restored.json()["archived_at"] is None
    assert client.post(path + "/scans").status_code == 202
    assert [e["action"] for e in client.get(path + "/history").json()["items"]] == [
        "restored",
        "archived",
        "created",
    ]


def test_active_scan_prevents_source_mutation(client, monkeypatch, remote_source):
    source, payload = remote_source
    monkeypatch.setattr("app.api.main.enqueue", lambda *args: None)
    path = f"/api/sources/{source['id']}"
    job = client.post(path + "/scans").json()
    assert client.put(path, json={**payload, "expected_revision": 1}).status_code == 409
    assert client.post(path + "/archive", json={"archived": True, "expected_revision": 1}).status_code == 409
    assert client.post(path + "/scans").json()["id"] == job["id"]
    client.post(f"/api/scans/{job['id']}/cancel")
    assert client.put(path, json={**payload, "expected_revision": 1}).status_code == 200


def test_scan_uses_snapshot_and_edit_preserves_observed_access(client, monkeypatch, remote_source):
    source, payload = remote_source
    monkeypatch.setattr("app.api.main.enqueue", lambda *args: None)
    path = f"/api/sources/{source['id']}"
    job = client.post(path + "/scans").json()
    assert job["source_snapshot"]["revision"] == 1
    # Simulate a later operator change outside the API; execution still uses the captured scope.
    with SessionLocal() as db:
        row = db.get(Source, source["id"])
        row.access_context = "public_observed"
        row.config = {**row.config, "max_depth": 2}
        db.commit()
    seen = []

    def collect(config, staging, cancelled):
        from app.connectors import Collection, Item

        seen.append(config)
        content = staging / "fixture.txt"
        content.write_text("SYNTHETIC\napi_key=synthetic-snapshot-secret-123456")
        return Collection(items=[Item(content, "fixture.txt", payload["config"]["url"])])

    monkeypatch.setattr("app.workers.jobs.http.collect", collect)
    run_scan(job["id"])
    assert seen[0]["max_depth"] == 0
    incident = client.get("/api/incidents").json()["items"][0]
    detail = client.get(f"/api/incidents/{incident['id']}").json()
    assert detail["policy"]["inputs"]["access_context"] == "authorized_private"
    assert detail["occurrences"][0]["access_context"] == "authorized_private"
    assert (
        client.put(
            path, json={**payload, "access_context": "public_observed", "expected_revision": 1}
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/incidents/{incident['id']}").json()["occurrences"][0]["access_context"]
        == "authorized_private"
    )
    assert (
        client.get(f"/api/scans?source_id={source['id']}").json()["items"][0]["source_snapshot"][
            "access_context"
        ]
        == "authorized_private"
    )


def test_source_pagination_search_and_workspace_scope(client, other_client):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "analyst1@example.test"))
        for n in range(55):
            db.add(Source(workspace_id=user.workspace_id, name=f"Source {n:02}", kind="upload", config={}))
        db.commit()
    first = client.get("/api/sources?limit=50").json()
    second = client.get("/api/sources?limit=50&offset=50").json()
    assert first["total"] == 55 and len(second["items"]) == 5
    assert not {s["id"] for s in first["items"]} & {s["id"] for s in second["items"]}
    assert client.get("/api/sources?q=source%2054").json()["total"] == 1
    assert client.get("/api/sources?q=%25").json()["total"] == 0
    assert other_client.get("/api/sources?state=all").json()["total"] == 0
    assert client.get("/api/sources?state=typo").status_code == 422


def test_source_mutations_are_scoped_and_read_only(client, other_client, monkeypatch, remote_source):
    source, payload = remote_source
    path = f"/api/sources/{source['id']}"
    body = {**payload, "expected_revision": 1}
    assert other_client.put(path, json=body).status_code == 404
    assert (
        other_client.post(path + "/archive", json={"archived": True, "expected_revision": 1}).status_code
        == 404
    )
    assert other_client.get(path + "/history").status_code == 404
    assert other_client.get(f"/api/scans?source_id={source['id']}").status_code == 404
    assert client.put(path, json=body, headers={"x-csrf-token": ""}).status_code == 403
    from app.config import settings

    monkeypatch.setattr(settings(), "public_read_only", True)
    assert client.put(path, json=body).status_code == 403
    assert client.post(path + "/archive", json={"archived": True, "expected_revision": 1}).status_code == 403
