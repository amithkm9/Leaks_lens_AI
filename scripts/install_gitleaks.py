"""Install the pinned official binary in project-local .data/bin, verifying SHA-256."""

import hashlib
import platform
import tarfile
import urllib.request
from pathlib import Path

VERSION = "8.30.1"
root = Path(__file__).resolve().parents[1] / ".data"
root.mkdir(exist_ok=True, mode=0o700)
system = {"Darwin": "darwin", "Linux": "linux"}.get(platform.system())
arch = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "AMD64": "x64"}.get(
    platform.machine()
)
if not system or not arch:
    raise SystemExit(
        "This installer supports macOS/Linux arm64 and x64; install Gitleaks manually elsewhere."
    )
name = f"gitleaks_{VERSION}_{system}_{arch}.tar.gz"
base = f"https://github.com/gitleaks/gitleaks/releases/download/v{VERSION}/"
archive = root / name
urllib.request.urlretrieve(base + name, archive)
checksums = (
    urllib.request.urlopen(base + f"gitleaks_{VERSION}_checksums.txt", timeout=30)
    .read()
    .decode()
)
expected = next(
    line.split()[0] for line in checksums.splitlines() if line.endswith(name)
)
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit("Checksum mismatch; no executable was installed")
binary = root / "bin" / "gitleaks"
binary.parent.mkdir(exist_ok=True, mode=0o700)
with tarfile.open(archive) as tar:
    binary.write_bytes(tar.extractfile("gitleaks").read())
binary.chmod(0o755)
print(f"Installed Gitleaks {VERSION}; checksum verified.")
