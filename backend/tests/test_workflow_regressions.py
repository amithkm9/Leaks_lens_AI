from app.analysis import get_analysis
from app.db import SessionLocal, engine, get_db
from app.models import Document, Incident
from conftest import upload
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session


def test_reanalysis_retires_both_sides_of_current_relationships(client, monkeypatch):
    first, _ = upload(client, "SYNTHETIC first\napi_key=shared-synthetic-value-123456")
    second, job = upload(client, "SYNTHETIC second\napi_key=shared-synthetic-value-123456")
    with SessionLocal() as db:
        left = db.get(Incident, first["id"])
        right = db.get(Incident, second["id"])
        assert left.related[0]["document_id"] == right.document_id
        original = get_analysis(db, db.get(Document, right.document_id))
        assert original.related[0]["document_id"] == left.document_id
    import app.workers.analysis as worker

    monkeypatch.setattr(worker, "detect", lambda text: ("Controlled negative result", [], []))
    response = client.post(
        f"/api/incidents/{second['id']}/reanalyses",
        json={
            "source_id": job["source_id"],
            "expected_analysis_revision": 1,
            "reason": "Reevaluate relationship",
        },
    )
    assert response.status_code == 202
    with SessionLocal() as db:
        assert db.get(Incident, first["id"]).related == []
        assert db.get(Incident, second["id"]).related == []
        assert get_analysis(db, db.get(Document, second["document_id"]), 1).related == original.related


def test_incident_list_query_budget_does_not_grow_per_document(client):
    for n in range(4):
        upload(client, f"SYNTHETIC {n}\napi_key=synthetic-value-{n}-123456")
    statements = []

    def count_queries(connection, cursor, statement, params, context, many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", count_queries)
    try:
        response = client.get("/api/incidents")
    finally:
        event.remove(engine, "before_cursor_execute", count_queries)
    assert response.status_code == 200 and response.json()["total"] == 4
    assert len(statements) <= 6, len(statements)


def test_readiness_rejects_database_missing_analysis_migration(client, tmp_path):
    from app.api.main import app

    temporary = create_engine(f"sqlite:///{tmp_path}/outdated.db", connect_args={"check_same_thread": False})
    with temporary.begin() as db:
        db.execute(text("CREATE TABLE users (id TEXT)"))

    def old_database():
        with Session(temporary) as db:
            yield db

    app.dependency_overrides[get_db] = old_database
    try:
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert "OperationalError" not in response.text
    finally:
        app.dependency_overrides.pop(get_db)
        temporary.dispose()
    assert client.get("/api/ready").status_code == 200
