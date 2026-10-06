"""Disposable browser-test database and account; never seeds the user's database."""

import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="leaklens-e2e-") as directory:
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{directory}/browser.db",
        "DATA_DIR": directory,
        "FINGERPRINT_KEY": "synthetic-browser-test-only-" * 3,
        "JOB_MODE": "local",
        "ENVIRONMENT": "development",
        "LOCAL_REPO_ROOT": str(Path(directory) / "repos"),
        "LLM_MODE": "offline",
        "ANTHROPIC_API_KEY": "",
        "PUBLIC_READ_ONLY": "false",
        "COOKIE_SECURE": "false",
        "ALLOWED_ORIGIN": "http://127.0.0.1:5174",
        "LEAKLENS_SETUP_PASSWORD": "Synthetic-browser-only-123",
        "PATH": str(root / ".data/bin") + os.pathsep + os.environ["PATH"],
    }
    python = str(root / "backend/.venv/bin/python")
    subprocess.run(
        [str(root / "backend/.venv/bin/alembic"), "upgrade", "head"],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    subprocess.run(
        [
            python,
            "-m",
            "app.cli",
            "create-user",
            "--email",
            "browser@example.test",
            "--workspace",
            "Browser verification",
        ],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    # A local, non-network fixture exercises source editing and real Git scans.
    repo = Path(env["LOCAL_REPO_ROOT"]) / "browser-fixture"
    repo.mkdir(parents=True)
    (repo / "fixture.txt").write_text(
        "SYNTHETIC public browser fixture. No sensitive content.\n"
    )
    for args in (
        ["init"],
        ["add", "fixture.txt"],
        ["commit", "-m", "Synthetic browser fixture"],
    ):
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=browser@example.test",
                "-c",
                "user.name=Synthetic",
                "-c",
                "core.hooksPath=/dev/null",
                *args,
            ],
            cwd=repo,
            env=env,
            check=True,
            capture_output=True,
        )
    subprocess.run(
        [
            python,
            "-c",
            """
from pathlib import Path
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import Source, User
from app.sources import record_event
with SessionLocal() as db:
    user = db.scalar(select(User).where(User.email == 'browser@example.test'))
    source = Source(workspace_id=user.workspace_id, name='Synthetic editable repository', kind='git',
                    access_context='authorized_private',
                    config={'path': str(settings().local_repo_root / 'browser-fixture'),
                            'history_commits': 1, 'max_documents': 10})
    db.add(source)
    db.flush()
    record_event(db, source, 'created', user.id)
    db.commit()
""",
        ],
        cwd=root / "backend",
        env=env,
        check=True,
    )
    subprocess.run(
        [
            str(root / "backend/.venv/bin/uvicorn"),
            "app.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
        cwd=root / "backend",
        env=env,
        check=True,
    )
