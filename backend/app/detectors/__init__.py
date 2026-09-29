import hashlib
import hmac
import importlib.metadata
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from app.config import settings

SECRET = re.compile(
    r"""(?im)(?:api[_-]?key|secret|password|access[_-]?token|auth[_-]?token)["']?\s*[=:]\s*["']?([^\s"',;}]{6,})"""
)
TOKEN = re.compile(r"\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b")
EMAIL = re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE = re.compile(r"(?<!\w)(?:\+\d[\d ()-]{8,}\d)(?!\w)")
QUERY = re.compile(r"(?i)([?&](?:token|key|api_key|secret|password|signature|auth|code)=)[^&#\s]+")
AUTH = re.compile(r"(?im)(authorization\s*[:=]\s*)(?:bearer|basic)?\s*[^\r\n]+")
PLACEHOLDERS = {
    "changeme",
    "your_api_key",
    "example",
    "placeholder",
    "xxxxxx",
    "example_key",
    "not-a-real-secret",
}


def fingerprint(value):
    key = settings().fingerprint_key
    if len(key) < 32:
        raise ValueError("FINGERPRINT_KEY must contain at least 32 characters; run setup")
    return hmac.new(key.encode(), value.encode(), hashlib.sha256).hexdigest()


def safe_text(text):
    """Defense-in-depth sanitizer for metadata and analyst/provider output."""
    text = AUTH.sub(r"\1[REDACTED_AUTH]", str(text))
    text = QUERY.sub(r"\1[REDACTED]", text)
    text = SECRET.sub(lambda m: m.group(0).replace(m.group(1), "[REDACTED_SECRET]"), text)
    text = TOKEN.sub("[REDACTED_SECRET]", text)
    text = EMAIL.sub("[REDACTED_EMAIL]", text)
    return PHONE.sub("[REDACTED_PHONE]", text)


def sanitize(value):
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, dict):
        return {safe_text(k): sanitize(v) for k, v in value.items()}
    return value


def availability():
    try:
        presidio = importlib.metadata.version("presidio-analyzer")
    except importlib.metadata.PackageNotFoundError:
        presidio = None
    gitleaks = shutil.which("gitleaks")
    return {
        "custom": "1.0",
        "presidio": presidio,
        "gitleaks": bool(gitleaks),
        "pii_entities": ["EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD"],
        "ocr": False,
    }


def detect(text):
    hits, warnings = [], []

    def add(start, end, kind, detector, version="1.0", score=None):
        if end <= start:
            return
        value = text[start:end]
        hits.append(
            dict(
                start=start,
                end=end,
                finding_type=kind,
                detector=detector,
                detector_version=version,
                score=score,
                fingerprint=fingerprint(value),
                placeholder=value.lower() in PLACEHOLDERS,
            )
        )

    for match in SECRET.finditer(text):
        add(*match.span(1), "SUSPECTED_SECRET", "leaklens-patterns")
    for match in TOKEN.finditer(text):
        add(*match.span(), "SUSPECTED_SECRET", "leaklens-patterns")
    # Structured exports put the secret label in the header, not beside each value.
    columns = []
    offset = 0
    for line in text.splitlines(keepends=True):
        cells = line.rstrip("\r\n").split(",")
        secret_columns = [
            i
            for i, cell in enumerate(cells)
            if re.fullmatch(
                r"(?i)(?:api[_-]?key|secret|password|access[_-]?token|auth[_-]?token)",
                cell.strip().strip('"'),
            )
        ]
        if len(cells) > 1 and secret_columns:
            columns = secret_columns
        elif columns and len(cells) > max(columns):
            for column in columns:
                value = cells[column].strip().strip('"')
                if value:
                    cell_start = sum(len(c) + 1 for c in cells[:column])
                    start = offset + cell_start + cells[column].find(value)
                    add(start, start + len(value), "SUSPECTED_SECRET", "leaklens-csv-columns")
        offset += len(line)

    try:
        from presidio_analyzer.predefined_recognizers import (
            EmailRecognizer,
            PhoneRecognizer,
            CreditCardRecognizer,
        )

        version = importlib.metadata.version("presidio-analyzer")
        from tldextract import TLDExtract

        offline_suffixes = TLDExtract(suffix_list_urls=(), cache_dir=None)

        class OfflineEmailRecognizer(EmailRecognizer):
            def validate_result(self, pattern_text):
                return bool(offline_suffixes(pattern_text).fqdn)

        for recognizer in (OfflineEmailRecognizer(), PhoneRecognizer(), CreditCardRecognizer()):
            for result in recognizer.analyze(text, recognizer.supported_entities, nlp_artifacts=None):
                add(result.start, result.end, result.entity_type, "presidio", version, result.score)
    except Exception:
        warnings.append("Presidio unavailable; only fallback email/phone patterns were applied")
        for regex, kind in ((EMAIL, "EMAIL_ADDRESS"), (PHONE, "PHONE_NUMBER")):
            for match in regex.finditer(text):
                add(*match.span(), kind, "leaklens-fallback")
    # Reserved/internal domains are intentionally absent from public suffix lists.
    for match in EMAIL.finditer(text):
        if not any(h["start"] == match.start() and h["end"] == match.end() for h in hits):
            add(*match.span(), "EMAIL_ADDRESS", "leaklens-email")
    binary = shutil.which("gitleaks")
    if binary:
        with tempfile.TemporaryDirectory(prefix="leaklens-detector-") as tmp:
            root = Path(tmp)
            scan = root / "input"
            scan.mkdir(mode=0o700)
            (scan / "content.txt").write_text(text)
            report = root / "report.json"
            try:
                proc = subprocess.run(
                    [
                        binary,
                        "dir",
                        str(scan),
                        "--no-banner",
                        "--ignore-gitleaks-allow",
                        "--exit-code",
                        "0",
                        "--report-format",
                        "json",
                        "--report-path",
                        str(report),
                    ],
                    capture_output=True,
                    timeout=25,
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp},
                )
                if proc.returncode != 0:
                    raise ValueError("Detector failed")
                version = (
                    subprocess.run([binary, "version"], capture_output=True, timeout=3)
                    .stdout.decode()
                    .strip()[:40]
                )
                for item in json.loads(report.read_text() if report.exists() else "[]"):
                    secret = item.get("Secret", "")
                    if secret:
                        for match in re.finditer(re.escape(secret), text):
                            add(*match.span(), "SUSPECTED_SECRET", "gitleaks", version)
            except Exception:
                warnings.append("Gitleaks failed or timed out; custom secret patterns only")
    else:
        warnings.append("Gitleaks is not installed; custom secret patterns only")
    # Keep one deterministic hit per span/type, preferring Gitleaks over custom rules.
    unique = {}
    for hit in hits:
        unique[(hit["start"], hit["end"], hit["finding_type"])] = hit
    hits = sorted(unique.values(), key=lambda x: (x["start"], -x["end"]))
    mask = list(text)
    for hit in hits:
        mask[hit["start"] : hit["end"]] = ["█"] * (hit["end"] - hit["start"])
    # Preserve line and character coordinates for evidence citations.
    redacted = "".join(mask)
    redacted = AUTH.sub(lambda m: m.group(1) + "█" * (len(m.group(0)) - len(m.group(1))), redacted)
    redacted = QUERY.sub(lambda m: m.group(1) + "█" * (len(m.group(0)) - len(m.group(1))), redacted)
    return redacted, hits, warnings
