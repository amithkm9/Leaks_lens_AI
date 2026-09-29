"""Run inside the API container. Temporary account; cleans only its own records."""

import json
import secrets
import time
import httpx
from sqlalchemy import delete, select
from app.db import Base, SessionLocal
from app.models import Workspace, User, Session, Incident, Evidence
from app.security import passwords
from app.config import settings

workspace_id = None
user_id = None
try:
    with SessionLocal() as db:
        workspace = Workspace(name="Temporary Compose verification")
        db.add(workspace)
        db.flush()
        password = secrets.token_urlsafe(28)
        email = "verify-" + secrets.token_hex(8) + "@example.test"
        user = User(
            workspace_id=workspace.id,
            email=email,
            password_hash=passwords.hash(password),
        )
        db.add(user)
        db.commit()
        workspace_id, user_id = workspace.id, user.id
    with httpx.Client(
        base_url="http://frontend:8080",
        timeout=15,
        headers={"Origin": settings().allowed_origin},
    ) as client:
        page = client.get("/")
        assert page.status_code == 200 and "LeakLens AI" in page.text
        assert client.get("/api/ready").status_code == 200
        response = client.post(
            "/api/auth/login", json={"email": email, "password": password}
        )
        response.raise_for_status()
        client.headers["x-csrf-token"] = response.json()["csrf_token"]
        assert client.get("/api/auth/me").json()["email"] == email
        source = client.post(
            "/api/uploads",
            files={
                "file": (
                    "synthetic-compose.csv",
                    b"SYNTHETIC TEST\norganization,api_key\nTest,synthetic-compose-secret-abcdef123456",
                )
            },
        )
        source.raise_for_status()
        job_id = source.json()["id"]
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            job = client.get("/api/scans/" + job_id).json()
            if job["status"] not in {"queued", "running"}:
                break
            time.sleep(0.5)
        assert job["status"] == "completed", job
        assert job["processed"] == 1, job
        incident = client.get("/api/incidents").json()["items"][0]
        detail = client.get("/api/incidents/" + incident["id"]).json()
        assert "synthetic-compose-secret-abcdef123456" not in json.dumps(detail)
        run = client.post(
            "/api/incidents/" + incident["id"] + "/investigations",
            json={"mode": "offline"},
        ).json()
        while time.monotonic() < deadline:
            investigation = client.get("/api/investigations/" + run["id"]).json()
            if investigation["status"] not in {"queued", "running"}:
                break
            time.sleep(0.5)
        assert investigation["status"] == "completed", investigation
        assert (
            client.post(
                "/api/incidents/" + incident["id"] + "/reviews",
                json={"action": "confirm", "reason": "Synthetic Compose verification"},
            ).status_code
            == 201
        )
        exported = client.get("/api/incidents/" + incident["id"] + "/export")
        assert (
            exported.status_code == 200
            and "synthetic-compose-secret-abcdef123456" not in exported.text
        )
        print(
            json.dumps(
                {
                    "frontend_proxy_login_session": "passed",
                    "postgresql_migration": "passed",
                    "redis_worker_upload": "passed",
                    "redaction": "passed",
                    "offline_investigation": "passed",
                    "review_export": "passed",
                    "job_id": job_id,
                }
            )
        )
finally:
    if workspace_id:
        with SessionLocal() as db:
            from app.models import Source

            sources = db.scalars(
                select(Source).where(Source.workspace_id == workspace_id)
            ).all()
            for source in sources:
                (settings().data_dir / "uploads" / source.id).unlink(missing_ok=True)
            db.execute(delete(Session).where(Session.user_id == user_id))
            for table in reversed(Base.metadata.sorted_tables):
                if "workspace_id" in table.c:
                    db.execute(
                        delete(table).where(table.c.workspace_id == workspace_id)
                    )
            db.execute(delete(Workspace).where(Workspace.id == workspace_id))
            db.commit()
