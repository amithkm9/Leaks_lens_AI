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
