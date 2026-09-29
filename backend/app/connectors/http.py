import http.client
import socket
import ssl
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
from app.config import settings
from app.connectors import Collection, Item
from app.connectors.policy import validate_url, AccessDenied
from app.detectors import safe_text
from app.parsers import supported


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for key, value in attrs:
                if key == "href" and value and len(self.links) < 500:
                    self.links.append(value)


def fetch(url, config):
    """Pin connections to validated IPs; TLS still verifies the original hostname."""
    for _ in range(6):
        p, addresses = validate_url(url, config)
        port = p.port or (443 if p.scheme == "https" else 80)
        connection = http.client.HTTPConnection(p.hostname, port, timeout=12)
        sock = socket.create_connection((addresses[0], port), timeout=12)
        if p.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=p.hostname)
        connection.sock = sock
        try:
            connection.request(
                "GET",
                p.path or "/",
                headers={
                    "Host": p.netloc,
                    "User-Agent": "LeakLens/0.1 authorized-source-monitor",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Redirect lacks a destination")
                url = urljoin(url, location)
                continue
            if response.status in {404, 410}:
                return response.status, b"", "", url
            if response.status != 200:
                raise ValueError(f"Source returned HTTP {response.status}")
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise ValueError("Compressed HTTP content is not supported")
            length = response.getheader("Content-Length")
            if length and int(length) > settings().max_file_bytes:
                raise ValueError("Document exceeds byte limit")
            data = response.read(settings().max_file_bytes + 1)
            if len(data) > settings().max_file_bytes:
                raise ValueError("Document exceeds byte limit")
            return 200, data, response.getheader("Content-Type", ""), url
        finally:
            connection.close()
    raise AccessDenied("Redirect limit exceeded")


def collect(config, staging, cancelled=lambda: False):
    result = Collection()
    pending, seen = [(config["url"], 0), *((url, 0) for url in config.get("known_urls", []))], set()
    limit = min(config.get("max_documents", 100), settings().max_documents)
    while pending and len(seen) < limit:
        if cancelled():
            result.complete = False
            result.warnings.append("Collection cancelled")
            break
        url, depth = pending.pop(0)
        url = urldefrag(url)[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            for attempt in range(2):
                try:
                    status, data, content_type, final = fetch(url, config)
                    break
                except (OSError, http.client.HTTPException):
                    if attempt:
                        raise ValueError("Source connection failed after retry") from None
            if status in {404, 410}:
                result.absent.append(url)
                continue
            name = Path(urlsplit(final).path).name or "document.txt"
            if "text/html" in content_type:
                parser = Links()
                parser.feed(data.decode("utf-8", errors="replace"))
                if depth < config.get("max_depth", 1):
                    for link in parser.links:
                        target = urldefrag(urljoin(final, link))[0]
                        try:
                            validate_url(target, config)
                        except AccessDenied:
                            continue
                        pending.append((target, depth + 1))
                elif parser.links:
                    result.warnings.append("Link depth limit reached; deeper links were not visited")
                    result.complete = False
            elif supported(name):
                path = staging / str(len(result.items))
                path.write_bytes(data)
                result.items.append(Item(path, name, url))
            else:
                result.warnings.append(f"Unsupported file skipped: {safe_text(name)}")
                result.complete = False
        except ValueError as exc:
            result.errors.append(safe_text(str(exc)))
            result.complete = False
        time.sleep(settings().http_rate_seconds)
    if pending:
        result.warnings.append("HTTP request limit reached; some documents were not visited")
        result.complete = False
    result.checkpoint = {"visited": len(seen), "documents": len(result.items)}
    return result
