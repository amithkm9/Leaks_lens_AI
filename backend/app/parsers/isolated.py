"""Executed as a short-lived subprocess. Receives only a bounded staged file."""

import csv
import io
import json
import sys
from pathlib import Path


def parse(path, name, limits):
    suffix = Path(name).suffix.lower()
    data = Path(path).read_bytes()
    if len(data) > limits["bytes"]:
        raise ValueError("File exceeds byte limit")
    warnings = []
    meta = {"bytes": len(data), "format": suffix.lstrip("."), "rows": None}
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        meta["pages"] = len(reader.pages)
        if len(reader.pages) > limits["pages"]:
            warnings.append("PDF page limit reached; remaining pages were not scanned")
        text = "\n".join((p.extract_text() or "") for p in reader.pages[: limits["pages"]])
        if not text.strip():
            warnings.append("No extractable text; image-only PDFs require OCR, which is unavailable")
    else:
        if b"\x00" in data:
            raise ValueError("Binary files are not supported")
        text = data.decode("utf-8-sig", errors="strict")
        if suffix == ".json":
            json.loads(text)
        if suffix == ".csv":
            csv.field_size_limit(1_000_000)
            rows = []
            for i, row in enumerate(csv.reader(io.StringIO(text), strict=True)):
                if i > limits["rows"]:
                    warnings.append("CSV row limit reached; remaining rows were not scanned")
                    break
                rows.append(row)
            meta["rows"] = max(0, len(rows) - 1)
            text = "\n".join(",".join(row) for row in rows)
    if len(text) > limits["chars"]:
        warnings.append("Text character limit reached; remaining content was not scanned")
        text = text[: limits["chars"]]
    return {"text": text, "metadata": meta, "warnings": warnings}


if __name__ == "__main__":
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
        if sys.platform == "linux":
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        result = parse(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]))
        print(json.dumps(result))
    except Exception as exc:
        # Parser exception messages can contain original document text.
        print(json.dumps({"error": f"File could not be parsed ({type(exc).__name__})"}))
        sys.exit(1)
