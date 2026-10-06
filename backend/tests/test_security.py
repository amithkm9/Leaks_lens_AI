import socket
from types import SimpleNamespace

import pytest
from app.agent.runner import validate_result
from app.attribution import attribute
from app.config import settings
from app.connectors.policy import AccessDenied, local_repository, validate_url
from app.correlation import shingles, similarity
from app.detectors import detect, safe_text
from app.parsers import parse_file


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",
        "http://169.254.169.254/latest",
        "file:///etc/passwd",
        "http://user:pass@example.com/x",
        "http://localhost/x",
        "http://[::1]/x",
    ],
)
def test_ssrf(url):
    with pytest.raises(AccessDenied):
        validate_url(
            url,
            {
                "allowed_hosts": ["127.0.0.1", "169.254.169.254", "localhost", "::1", "example.com"],
                "path_prefixes": ["/"],
            },
        )


def test_public_path_boundaries(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443))])
    config = {"allowed_hosts": ["files.example.com"], "path_prefixes": ["/approved"]}
    validate_url("https://files.example.com/approved/file.csv", config)
    for url in [
        "https://files.example.com/approved-evil/a",
        "https://files.example.com/approved/%252e%252e/private",
        "https://evil.example/approved/a",
        "https://files.example.com/approved/a?token=synthetic-secret",
    ]:
        with pytest.raises(AccessDenied):
            validate_url(url, config)


def test_mixed_dns_answers(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("10.0.0.1", 443))],
    )
    with pytest.raises(AccessDenied):
        validate_url("https://example.com/x", {"allowed_hosts": ["example.com"], "path_prefixes": ["/"]})


def test_masking():
    raw = "api_key=synthetic-only-abcdef123456\nAuthorization: Bearer synthetic-header\nhttps://example.test/?token=synthetic-query\nada@example.test\n+33 6 12 34 56 78"
    redacted, hits, _ = detect(raw)
    for value in [
        "synthetic-only-abcdef123456",
        "synthetic-header",
        "synthetic-query",
        "ada@example.test",
        "+33 6 12 34 56 78",
    ]:
        assert value not in redacted and value not in safe_text(raw)
    assert hits and len(redacted) == len(raw)


def test_similarity_and_conflicting_orgs():
    raw = "synthetic customer export details for organization alpha approved records phone address contact"
    assert similarity(shingles(raw), shingles(raw)) == 1
    assert similarity(shingles(raw), shingles("unrelated weather report sunny tomorrow")) == 0
    orgs = [
        SimpleNamespace(
            id=str(n),
            name=f"Company {n}",
            domains=[f"company{n}.test"],
            aliases=[],
            reference_ids=[],
            importance="normal",
        )
        for n in (1, 2)
    ]
    assert all(
        a["assessment"] == "multiple_candidates" for a in attribute("company1.test company2.test", orgs)
    )


def test_citation_validation():
    base = {
        "category": "unknown",
        "proposed_organization": None,
        "supporting_evidence_ids": ["fake"],
        "assessment": "concerning",
        "summary": "test",
        "uncertainty": [],
        "missing_information": [],
        "suggested_next_steps": [],
    }
    with pytest.raises(ValueError, match="citation"):
        validate_result(base, {"real"}, set())
    base.update(supporting_evidence_ids=["real"], proposed_organization="wrong")
    with pytest.raises(ValueError, match="organization"):
        validate_result(base, {"real"}, {"right"})
    base.update(supporting_evidence_ids=[], proposed_organization=None)
    with pytest.raises(ValueError, match="claim"):
        validate_result(base, set(), set())


def test_parser_limits(tmp_path, monkeypatch):
    monkeypatch.setattr(settings(), "max_csv_rows", 2)
    path = tmp_path / "input"
    path.write_text("name,email\na,a@example.test\nb,b@example.test\nc,c@example.test")
    result = parse_file(path, "input.csv")
    assert result["warnings"] and result["metadata"]["rows"] == 2 and "c@example.test" not in result["text"]
    path.write_bytes(b"%PDF-malformed")
    with pytest.raises(ValueError):
        parse_file(path, "bad.pdf")
    with pytest.raises(AccessDenied):
        local_repository(str(tmp_path))


def test_json_and_csv_secret_values_are_masked():
    for raw in [
        '{"api_key": "synthetic-json-secret-123456"}',
        "SYNTHETIC\ncompany,api_key\nExample,synthetic-csv-secret-123456",
    ]:
        redacted, hits, _ = detect(raw)
        assert "synthetic-json-secret-123456" not in redacted
        assert "synthetic-csv-secret-123456" not in redacted
        assert any(h["finding_type"] == "SUSPECTED_SECRET" for h in hits)


def test_redirect_revalidates_destination_and_pins_ip(monkeypatch):
    from app.connectors import http

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("93.184.216.34", 80))])
    connected = []
    monkeypatch.setattr(
        socket, "create_connection", lambda destination, **kw: connected.append(destination) or object()
    )

    class Response:
        status = 302

        def getheader(self, name, default=None):
            return "http://169.254.169.254/latest/meta-data/" if name == "Location" else default

    class Connection:
        def __init__(self, *a, **kw):
            pass

        def request(self, *a, **kw):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(http.http.client, "HTTPConnection", Connection)
    with pytest.raises(AccessDenied):
        http.fetch(
            "http://files.example.com/approved/",
            {"allowed_hosts": ["files.example.com"], "path_prefixes": ["/approved"]},
        )
    assert connected == [("93.184.216.34", 80)]
