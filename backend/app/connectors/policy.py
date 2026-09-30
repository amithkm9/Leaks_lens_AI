import ipaddress
import posixpath
import socket
from urllib.parse import unquote, urlsplit, urlunsplit
from pathlib import Path
from app.config import settings


class AccessDenied(ValueError):
    pass


def validate_url(url, config):
    if len(url) > 2000 or any(ord(c) < 33 or ord(c) == 127 for c in url):
        raise AccessDenied("Invalid URL characters or length")
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password or p.fragment:
        raise AccessDenied("Only configured HTTP(S) URLs without credentials or fragments are supported")
    if p.query:
        raise AccessDenied("Source URLs must not contain query strings or credentials")
    host = p.hostname.lower()
    if host not in config.get("allowed_hosts", []):
        raise AccessDenied("Destination host is outside this source's allowlist")
    decoded = unquote(p.path or "/", errors="strict")
    if (
        "\\" in decoded
        or "%" in decoded
        or any(ord(c) < 32 or ord(c) == 127 for c in decoded)
        or any(segment in {".", ".."} for segment in decoded.split("/"))
    ):
        raise AccessDenied("Invalid URL path")
    normalized = posixpath.normpath(decoded)
    prefixes = config.get("path_prefixes", [])
    if not any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix.rstrip("/") + "/")
        for prefix in prefixes
    ):
        raise AccessDenied("Destination path is outside this source's allowlist")
    try:
        addresses = sorted(
            {
                entry[4][0]
                for entry in socket.getaddrinfo(
                    host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM
                )
            }
        )
    except OSError:
        raise AccessDenied("Destination DNS lookup failed") from None
    fixture = (
        settings().environment == "development"
        and settings().fixture_origin
        and urlunsplit((p.scheme, p.netloc, "", "", "")) == settings().fixture_origin
    )
    if not addresses or (not fixture and any(not ipaddress.ip_address(ip).is_global for ip in addresses)):
        raise AccessDenied("Private, loopback, reserved, and metadata addresses are blocked")
    return p, addresses


def local_repository(value):
    root = settings().local_repo_root.resolve()
    path = Path(value).expanduser().resolve()
    if (
        not path.is_relative_to(root)
        or path == root
        or not (path / ".git").is_dir()
        or (path / ".git").is_symlink()
    ):
        raise AccessDenied(
            "Local repositories must be inside LOCAL_REPO_ROOT and contain a regular .git directory"
        )
    return path
