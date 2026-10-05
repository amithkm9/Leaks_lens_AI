import json
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, text


def test_source_lifecycle_migrates_existing_data(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path}/migration.db", "DATA_DIR": str(tmp_path)}

    def migrate(*args):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *args], cwd=backend, env=env, capture_output=True, text=True
        )
        assert result.returncode == 0, result.stdout + result.stderr

    migrate("upgrade", "1e1084787a6a")
    engine = create_engine(env["DATABASE_URL"])
    with engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO workspaces (id, name, created_at) VALUES ('w', 'Legacy workspace', '2026-01-01')"
            )
        )
        db.execute(
            text("""INSERT INTO sources (id, workspace_id, created_at, name, kind, config,
            access_context, health, checkpoint) VALUES ('s', 'w', '2026-01-01', 'Legacy source',
            'http', '{}', 'authorized_private', 'completed', '{}')""")
        )
        db.execute(
            text("""INSERT INTO documents (id, workspace_id, created_at, content_hash, name,
            category, redacted_text, metadata_json, shingles) VALUES ('d', 'w', '2026-01-01',
            'synthetic', 'Legacy document', 'unknown', 'redacted', '{}', '[]')""")
        )
        for job_id, status in [("old", "completed"), ("pending", "queued")]:
            db.execute(
                text("""INSERT INTO scan_jobs (id, workspace_id, source_id, created_at,
                status, phase, processed, total, errors, warnings, cancel_requested, attempts)
                VALUES (:id, 'w', 's', '2026-01-01', :status, 'test', 0, 0, '[]', '[]', 0, 0)"""),
                {"id": job_id, "status": status},
            )
        db.execute(
            text("""INSERT INTO source_occurrences (id, workspace_id, source_id, document_id,
            created_at, locator, locator_hash, revision, state, first_observed, last_observed, last_job_id)
            VALUES ('o', 'w', 's', 'd', '2026-01-01', 'file.txt', 'synthetic', 'current', 'observed',
            '2026-01-01', '2026-01-01', 'old')""")
        )
    migrate("upgrade", "head")
    migrate("check")
    with engine.connect() as db:
        source = db.execute(text("SELECT revision, archived_at FROM sources")).one()
        assert source == (1, None)
        event = db.execute(text("SELECT action, user_id, snapshot FROM source_events")).one()
        assert event.action == "migrated" and event.user_id is None
        assert json.loads(event.snapshot)["name"] == "Legacy source"
        assert db.scalar(text("SELECT access_context FROM source_occurrences")) == "authorized_private"
        assert json.loads(db.scalar(text("SELECT source_snapshot FROM scan_jobs WHERE id='old'"))) == {}
        assert (
            json.loads(db.scalar(text("SELECT source_snapshot FROM scan_jobs WHERE id='pending'")))[
                "revision"
            ]
            == 1
        )
    migrate("downgrade", "1e1084787a6a")
    migrate("upgrade", "head")
    with engine.connect() as db:
        assert db.scalar(text("SELECT COUNT(*) FROM source_occurrences")) == 1
    engine.dispose()
