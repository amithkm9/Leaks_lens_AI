"""Opt-in billed smoke test; never enabled by the ordinary test command."""

import os
import pytest
from app.config import settings
from app.db import SessionLocal
from app.models import Incident, Investigation
from app.agent.runner import run_investigation
from conftest import upload


@pytest.mark.skipif(
    os.environ.get("LEAKLENS_RUN_LIVE_SMOKE") != "1",
    reason="Live provider smoke requires explicit opt-in and a server-side key",
)
def test_real_provider_tool_using_investigation(client):
    assert settings().anthropic_api_key, (
        "Configure ANTHROPIC_API_KEY locally; never paste it into test output or chat"
    )
    incident, _ = upload(client)
    with SessionLocal() as db:
        row = db.get(Incident, incident["id"])
        run = Investigation(
            workspace_id=row.workspace_id, incident_id=row.id, mode="live", model=settings().llm_model
        )
        db.add(run)
        db.commit()
        run_id = run.id
    run_investigation(run_id)
    result = client.get("/api/investigations/" + run_id).json()
    assert result["status"] == "completed", result.get("error")
    assert any(call["success"] for call in result["tool_calls"])
    assert result["usage"]["input_tokens"] > 0
    assert "synthetic-testing-secret-123456" not in str(result)
