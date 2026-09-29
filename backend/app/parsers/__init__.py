import json
import subprocess
import sys
from pathlib import Path
from app.config import settings

SUPPORTED = {
    ".pdf",
    ".csv",
    ".json",
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".sh",
    ".sql",
    ".xml",
    ".log",
    ".properties",
    ".java",
    ".go",
    ".rb",
    ".rs",
}


def supported(name):
    return Path(name).suffix.lower() in SUPPORTED or Path(name).name == ".env"


def parse_file(path: Path, name: str):
    cfg = settings()
    if not supported(name):
        raise ValueError("Unsupported format; use PDF, CSV, JSON, text, or source/configuration files")
    limits = dict(
        bytes=cfg.max_file_bytes, pages=cfg.max_pdf_pages, rows=cfg.max_csv_rows, chars=cfg.max_text_chars
    )
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-I",
                str(Path(__file__).with_name("isolated.py")),
                str(path),
                name,
                json.dumps(limits),
            ],
            capture_output=True,
            timeout=20,
            env={"PATH": "/usr/bin:/bin"},
        )
    except subprocess.TimeoutExpired:
        raise ValueError("Parser time limit exceeded") from None
    try:
        result = json.loads(proc.stdout)
    except (ValueError, UnicodeError):
        raise ValueError("Parser exceeded its limits or returned invalid output") from None
    if "error" in result:
        raise ValueError(result["error"])
    return result
