"""Generate private local configuration without overwriting existing settings."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = root / ".data"
data.mkdir(mode=0o700, exist_ok=True)
(data / "repos").mkdir(mode=0o700, exist_ok=True)
env = root / ".env"
if not env.exists():
    env.write_text(
        f'DATABASE_URL=sqlite:///{data}/leaklens.db\nDATA_DIR="{data}"\nLOCAL_REPO_ROOT="{data}/repos"\nFINGERPRINT_KEY={secrets.token_hex(32)}\nJOB_MODE=local\nALLOWED_ORIGIN=http://localhost:5173\nPOSTGRES_PASSWORD={secrets.token_urlsafe(32)}\n'
    )
    env.chmod(0o600)
    print("Created private .env. Create your analyst with make user.")
else:
    print("Existing .env preserved.")
