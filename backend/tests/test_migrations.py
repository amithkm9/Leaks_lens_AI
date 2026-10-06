import json
import os
import subprocess
import sys
from pathlib import Path

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
        db.execute(
            text("""INSERT INTO users (id, workspace_id, created_at, email, password_hash)
            VALUES ('u', 'w', '2026-01-01', 'legacy@example.test', 'unusable-synthetic-hash')""")
        )
        db.execute(
            text("""INSERT INTO incidents (id, workspace_id, created_at, updated_at, document_id,
            title, category, priority, status, summary, attribution, related, policy)
            VALUES ('i', 'w', '2026-01-01', '2026-01-01', 'd', 'Review legacy', 'unknown',
            'low', 'confirmed', 'Historical assessment', '[]', '[]', '{}')""")
        )
        db.execute(
            text("""INSERT INTO evidence (id, workspace_id, created_at, document_id, kind,
            location, excerpt, details) VALUES ('e', 'w', '2026-01-01', 'd', 'detection', '{}',
            'Historical excerpt', '{}')""")
        )
        db.execute(
            text("""INSERT INTO findings (id, workspace_id, created_at, document_id, evidence_id,
            finding_type, detector, detector_version, fingerprint, placeholder) VALUES ('f', 'w',
            '2026-01-01', 'd', 'e', 'SUSPECTED_SECRET', 'legacy', 'old', 'synthetic', false)""")
        )
        db.execute(
            text("""INSERT INTO reviews (id, workspace_id, created_at, incident_id, user_id,
            action, reason) VALUES ('r', 'w', '2026-01-01', 'i', 'u', 'confirm', 'Historical reason')""")
        )
        db.execute(
            text("""INSERT INTO investigations (id, workspace_id, created_at, incident_id,
            mode, status, prompt_version, result, usage) VALUES ('a', 'w', '2026-01-01', 'i',
            'offline', 'completed', 'v1', '{}', '{}')""")
        )
    migrate("upgrade", "head")
    migrate("check")
    with engine.connect() as db:
        analysis = db.execute(
            text(
                "SELECT document_id, revision, versions, redaction_status, redacted_text, summary FROM document_analyses"
            )
        ).one()
        assert analysis.document_id == "d" and analysis.revision == 1
        assert json.loads(analysis.versions) == {"legacy": True}
        assert analysis.redaction_status == "restricted" and analysis.redacted_text == "redacted"
        assert analysis.summary == "Historical assessment"
        assert db.scalar(text("SELECT analysis_revision FROM documents")) == 1
        for table in ("evidence", "findings", "reviews", "investigations"):
            assert db.scalar(text(f"SELECT analysis_revision FROM {table}")) == 1
        assert db.scalar(text("SELECT excerpt FROM evidence WHERE id='e'")) == "Historical excerpt"
        assert db.scalar(text("SELECT reason FROM reviews WHERE id='r'")) == "Historical reason"
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
    # Never silently flatten real revision history when rolling back to old code.
    with engine.begin() as db:
        db.execute(text("UPDATE document_analyses SET revision=2"))
    refused = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "7b42a8c91d03"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0 and "Versioned analyses exist" in refused.stderr
    with engine.connect() as db:
        assert db.scalar(text("SELECT revision FROM document_analyses")) == 2
    engine.dispose()
