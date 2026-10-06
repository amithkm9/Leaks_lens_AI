import json
import socket

import pytest
from fastmcp import Client
from pydantic import ValidationError
from sqlalchemy import select
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.api.middleware import RequestBodyLimitMiddleware
from app.config import Settings, settings
from app.connectors.policy import AccessDenied, validate_url
from app.db import SessionLocal
from app.detectors import detect, safe_text, sanitize
from app.models import Incident
from conftest import upload


def test_missing_account_still_checks_a_password_hash(client, monkeypatch):
    from app import security

    checked = []
    monkeypatch.setattr(
        security.passwords, "verify", lambda password, digest: checked.append(digest) or False
    )
    response = client.post("/api/auth/login", json={"email": "missing@example.test", "password": "wrong"})
    assert response.status_code == 401
    assert checked == [security.dummy_password_hash]


def test_login_throttle_is_bounded_and_expires(monkeypatch):
    from app.api.routes.auth import login_attempts, throttle_login
    from fastapi import HTTPException

    monkeypatch.setattr("app.api.routes.auth.time.monotonic", lambda: 100)
    for i in range(4096):
        throttle_login(str(i))
    with pytest.raises(HTTPException) as failure:
        throttle_login("new-client")
    assert failure.value.status_code == 429
    assert len(login_attempts) == 4096
    monkeypatch.setattr("app.api.routes.auth.time.monotonic", lambda: 161)
    throttle_login("new-client")
    assert list(login_attempts) == ["new-client"]


def test_login_throttle_blocks_repeated_attempts():
    from app.api.routes.auth import throttle_login
    from fastapi import HTTPException

    for _ in range(10):
        throttle_login("one-client")
    with pytest.raises(HTTPException) as failure:
        throttle_login("one-client")
    assert failure.value.status_code == 429


def test_failed_tls_handshake_closes_connection(monkeypatch):
    from app.connectors import http
    from urllib.parse import urlsplit
    from types import SimpleNamespace

    closed = []

    class Connection:
        sock = None

        def close(self):
            closed.append(self.sock)

    sock = object()
    monkeypatch.setattr(
        http, "validate_url", lambda *args: (urlsplit("https://example.com/a"), ["93.184.216.34"])
    )
    monkeypatch.setattr(http.http.client, "HTTPConnection", lambda *args, **kwargs: Connection())
    monkeypatch.setattr(http.socket, "create_connection", lambda *args, **kwargs: sock)

    def fail(*args, **kwargs):
        raise OSError("Synthetic TLS failure")

    monkeypatch.setattr(http.ssl, "create_default_context", lambda: SimpleNamespace(wrap_socket=fail))
    with pytest.raises(OSError):
        http.fetch("https://example.com/a", {})
    assert closed == [sock]


def test_structured_credentials_and_payment_data_are_sanitized():
    payload = {
        "nested": [{"api_key": "synthetic-sensitive-value", "Authorization": "Bearer synthetic-value"}],
        "clientSecret": "synthetic-client-value",
        "card_number": 4111111111111111,
        "summary": "Payment 4111 1111 1111 1111; postgres://analyst:synthetic-pass@db/app",
        "category": "configuration",
    }
    masked = sanitize(payload)
    encoded = json.dumps(masked)
    for value in (
        "synthetic-sensitive-value",
        "synthetic-value",
        "synthetic-client-value",
        "4111",
        "synthetic-pass",
    ):
        assert value not in encoded
    assert masked["category"] == "configuration"


@pytest.mark.parametrize(
    "raw,value",
    [
        ('{"password": "synthetic long pass phrase"}', "long pass phrase"),
        ("password='synthetic long pass phrase'", "long pass phrase"),
        ('{"Authorization": "Bearer synthetic-json-auth-value"}', "synthetic-json-auth-value"),
        ('{"password": "tiny"}', "tiny"),
        ('{"api_key": "synthetic \\"escaped\\" secret"}', "escaped"),
    ],
)
def test_quoted_credentials_are_fully_masked(raw, value):
    redacted, _, _ = detect(raw)
    assert value not in redacted
    assert value not in safe_text(raw)
    assert len(redacted) == len(raw)


def test_url_credentials_are_redacted_before_storage():
    raw = "SYNTHETIC\npostgres://analyst:synthetic-db-pass@database.test/app"
    redacted, hits, _ = detect(raw)
    assert "synthetic-db-pass" not in redacted
    assert "synthetic-db-pass" not in safe_text(raw)
    assert len(redacted) == len(raw)
    assert any(hit["finding_type"] == "SUSPECTED_SECRET" for hit in hits)


@pytest.mark.parametrize(
    "row",
    [
        '"Example, Inc",qwerty-Z987654321',
        '"Example\nCompany",qwerty-Z987654321',
        'Example,"qwerty-Z987654321,tail"',
        'Example,"qwerty-Z987654321\nsecond-line"',
        '"Example ""Company""",qwerty-Z987654321',
    ],
)
def test_quoted_csv_secrets_do_not_escape_redaction(client, row):
    incident, _ = upload(client, "SYNTHETIC\ncompany,api_key\n" + row, "quoted.csv")
    detail = client.get(f"/api/incidents/{incident['id']}").json()
    exported = client.get(f"/api/incidents/{incident['id']}/export").text
    assert "qwerty-Z987654321" not in json.dumps(detail)
    assert "qwerty-Z987654321" not in exported
    assert "second-line" not in detail["document"]["redacted_text"]
    assert "tail" not in detail["document"]["redacted_text"]
    assert any(f["detector"] == "leaklens-csv-columns" for f in detail["findings"])


@pytest.mark.parametrize(
    "path",
    [
        "/approved/%25252e%25252e/private.txt",
        "/approved/%2e%2e/private.txt",
        "/approved/./file.txt",
        "/approved/%255cprivate.txt",
        "/approved/file%0a.txt",
        "/approved/file\n.txt",
    ],
)
def test_ambiguous_paths_never_reach_dns(monkeypatch, path):
    def unexpected_dns(*args, **kwargs):
        pytest.fail("Malformed URL reached DNS resolution")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_dns)
    with pytest.raises(AccessDenied):
        validate_url(
            "https://files.example.com" + path,
            {"allowed_hosts": ["files.example.com"], "path_prefixes": ["/approved"]},
        )


@pytest.mark.parametrize(
    "values",
    [
        {"environment": "prod"},
        {"job_mode": "typo"},
        {"llm_mode": "typo"},
        {"max_file_bytes": 0},
        {"max_pdf_pages": -1},
        {"raw_retention_hours": -1},
        {"agent_max_tools": 7},
        {"agent_max_input_tokens": 0},
        {"input_price_per_million": -1},
        {"agent_max_cost_usd": float("nan")},
    ],
)
def test_invalid_safety_configuration_is_rejected(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_mcp_does_not_load_private_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=synthetic-provider-key\nLLM_MODEL=dotenv-model")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LEAKLENS_MCP_CASE", "test-case")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-inherited-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    # Bypass the cache without disturbing the fixture's database configuration.
    isolated = settings.__wrapped__()
    assert isolated.anthropic_api_key == ""
    assert isolated.llm_model != "dotenv-model"
    assert isolated.llm_mode == "offline"


def test_oversized_requests_are_rejected_before_parsing(client):
    response = client.post(
        "/api/uploads",
        content=b"invalid multipart",
        headers={"content-length": str(settings().max_file_bytes + 65537)},
    )
    assert response.status_code == 413
    response = client.post(
        "/api/organizations", content=b"x" * 65537, headers={"content-type": "application/json"}
    )
    assert response.status_code == 413
    assert client.get("/api/sources").json()["total"] == 0


def test_validation_errors_sanitize_untrusted_field_names(client):
    response = client.post(
        "/api/sources",
        json={
            "name": "Synthetic source",
            "kind": "http",
            "authorized": True,
            "config": {"api_key=synthetic-invalid-field-secret": "invalid"},
        },
    )
    assert response.status_code == 422
    assert "synthetic-invalid-field-secret" not in response.text


async def test_chunked_upload_is_bounded_and_parser_files_are_closed(monkeypatch):
    from starlette import formparsers

    monkeypatch.setattr(settings(), "max_file_bytes", 100)
    opened = []
    original = formparsers.SpooledTemporaryFile

    def track_file(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", track_file)

    async def endpoint(request):
        async with request.form():
            pytest.fail("Oversized upload reached the endpoint after parsing")
        return JSONResponse({})

    app = RequestBodyLimitMiddleware(Starlette(routes=[Route("/api/uploads", endpoint, methods=["POST"])]))
    messages = iter(
        [
            {
                "type": "http.request",
                "body": b'--test\r\nContent-Disposition: form-data; name="file"; filename="test.txt"\r\n\r\nhello',
                "more_body": True,
            },
            {"type": "http.request", "body": b"x" * 65637, "more_body": True},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    await app(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/uploads",
            "query_string": b"",
            "headers": [(b"content-type", b"multipart/form-data; boundary=test")],
        },
        receive,
        send,
    )
    assert sent[0]["status"] == 413
    assert opened and all(file.closed for file in opened)


async def test_mcp_citations_require_visible_content(client, monkeypatch):
    from app.mcp.server import mcp

    incident, _ = upload(
        client,
        "SYNTHETIC "
        + "x" * 6010
        + "\napi_key=synthetic-hidden-secret-123456",  # gitleaks:allow -- nonfunctional test fixture
    )
    with SessionLocal() as db:
        row = db.get(Incident, incident["id"])
        monkeypatch.setenv("LEAKLENS_MCP_WORKSPACE", row.workspace_id)
        monkeypatch.setenv("LEAKLENS_MCP_CASE", row.id)
    async with Client(mcp) as client_mcp:
        metadata = await client_mcp.call_tool(
            "get_document_metadata", {"document_id": incident["document_id"]}
        )
        assert metadata.data["evidence_ids"] == []
        content = await client_mcp.call_tool("get_redacted_content", {"document_id": incident["document_id"]})
        assert content.data["evidence_ids"] == []
        assert content.data["complete"] is False
        visible = await client_mcp.call_tool(
            "get_redacted_content",
            {
                "document_id": incident["document_id"],
                "bounded_location": 2,
            },
        )
        assert visible.data["evidence_ids"]
        assert "synthetic-hidden-secret-123456" not in str(visible.data)


async def test_mcp_related_links_do_not_expand_case_scope(client, monkeypatch):
    from app.mcp.server import mcp

    for number in range(3):
        upload(client, f"SYNTHETIC {number}\napi_key=synthetic-related-secret-{number}-123456")
    with SessionLocal() as db:
        cases = db.scalars(select(Incident).order_by(Incident.created_at)).all()
        first, second, third = cases
        first.related = [{"document_id": second.document_id}]
        second.related = [{"document_id": first.document_id}, {"document_id": third.document_id}]
        db.commit()
        monkeypatch.setenv("LEAKLENS_MCP_WORKSPACE", first.workspace_id)
        monkeypatch.setenv("LEAKLENS_MCP_CASE", first.id)
    async with Client(mcp) as client_mcp:
        links = await client_mcp.call_tool("find_related_documents", {"document_id": second.document_id})
        assert links.data["data"] == [{"document_id": first.document_id}]
        assert links.data["complete"] is False
        with pytest.raises(Exception):
            await client_mcp.call_tool("get_document_metadata", {"document_id": third.document_id})
