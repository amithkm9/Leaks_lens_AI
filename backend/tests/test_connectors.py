import subprocess
from app.config import settings
from app.connectors import http
from app.db import SessionLocal
from app.models import Source, User
from sqlalchemy import select


def test_git_history_repetition_symlink(client):
    repo = settings().local_repo_root / "history-test"
    repo.mkdir()

    def git(*args):
        subprocess.run(
            ["git", "-c", "user.email=synthetic@example.test", "-c", "user.name=Synthetic", *args],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    git("init")
    (repo / "config.env").write_text("SYNTHETIC\napi_key=synthetic-testing-secret-123456\n")
    git("add", ".")
    git("commit", "-m", "Synthetic version one")
    (repo / "config.env").write_text("SYNTHETIC version two\napi_key=synthetic-testing-secret-123456\n")
    (repo / "escape.txt").symlink_to("/etc/passwd")
    git("add", ".")
    git("commit", "-m", "Synthetic version two")
    response = client.post(
        "/api/sources",
        json={
            "name": "Test repository",
            "kind": "git",
            "authorized": True,
            "config": {"path": str(repo), "history_commits": 2},
        },
    )
    assert response.status_code == 201, response.text
    job = client.post(f"/api/sources/{response.json()['id']}/scans").json()
    result = client.get(f"/api/scans/{job['id']}").json()
    assert result["processed"] == 2, result
    assert any("Symlink" in w for w in result["warnings"])
    incidents = client.get("/api/incidents").json()["items"]
    assert len(incidents) == 2
    assert any(r["method"] == "keyed_secret_fingerprint" for i in incidents for r in i["related"])


def test_disappearance_vs_failure(client, monkeypatch):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "analyst1@example.test"))
        source = Source(
            workspace_id=user.workspace_id,
            name="Synthetic source",
            kind="http",
            access_context="public_observed",
            config={
                "url": "https://synthetic.test/config.txt",
                "allowed_hosts": ["synthetic.test"],
                "path_prefixes": ["/"],
            },
        )
        db.add(source)
        db.commit()
        sid = source.id
    monkeypatch.setattr(
        http,
        "fetch",
        lambda *a: (
            200,
            b"SYNTHETIC\napi_key=synthetic-testing-secret-123456",
            "text/plain",
            "https://synthetic.test/config.txt",
        ),
    )
    client.post(f"/api/sources/{sid}/scans")
    incident = client.get("/api/incidents").json()["items"][0]
    monkeypatch.setattr(http, "fetch", lambda *a: (_ for _ in ()).throw(ValueError("Connection failed")))
    client.post(f"/api/sources/{sid}/scans")
    assert client.get(f"/api/incidents/{incident['id']}").json()["occurrences"][0]["state"] == "unknown"
    monkeypatch.setattr(http, "fetch", lambda *a: (404, b"", "", "https://synthetic.test/config.txt"))
    client.post(f"/api/sources/{sid}/scans")
    assert client.get(f"/api/incidents/{incident['id']}").json()["occurrences"][0]["state"] == "not_observed"
