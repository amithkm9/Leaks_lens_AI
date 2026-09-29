import os
import tempfile
from pathlib import Path
import pytest

TEMP = tempfile.TemporaryDirectory(prefix="leaklens-tests-")
ROOT = Path(TEMP.name)
os.environ.update(
    DATABASE_URL=f"sqlite:///{ROOT}/tests.db",
    DATA_DIR=str(ROOT),
    FINGERPRINT_KEY="synthetic-test-key-" * 4,
    JOB_MODE="local",
    ENVIRONMENT="development",
    LLM_MODE="offline",
    ALLOWED_ORIGIN="http://testserver",
    LOCAL_REPO_ROOT=str(ROOT / "repos"),
)
from app.db import Base, engine, SessionLocal  # noqa: E402
from app.models import Workspace, User  # noqa: E402
from app.security import passwords  # noqa: E402
from app.api.main import app, login_attempts  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def database(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    login_attempts.clear()
    import app.api.main as api

    monkeypatch.setattr(api, "enqueue", lambda fn, identifier: fn(identifier))
    (ROOT / "repos").mkdir(exist_ok=True)
    with SessionLocal() as db:
        for n in (1, 2):
            w = Workspace(name=f"Workspace {n}")
            db.add(w)
            db.flush()
            db.add(
                User(
                    email=f"analyst{n}@example.test",
                    password_hash=passwords.hash("Synthetic-password-123"),
                    workspace_id=w.id,
                )
            )
        db.commit()
    yield


def authenticated(email):
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"email": email, "password": "Synthetic-password-123"})
    assert response.status_code == 200
    client.headers["x-csrf-token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def client():
    with authenticated("analyst1@example.test") as client:
        yield client


@pytest.fixture
def other_client():
    with authenticated("analyst2@example.test") as client:
        yield client


def upload(
    client,
    text="SYNTHETIC TEST INPUT\napi_key=synthetic-testing-secret-123456\ncontact=person@company.test\n",
    name="sample.env",
):
    response = client.post("/api/uploads", files={"file": (name, text.encode())})
    assert response.status_code == 202, response.text
    job = client.get(f"/api/scans/{response.json()['id']}").json()
    assert job["processed"] == 1, job
    return client.get("/api/incidents").json()["items"][0], job
