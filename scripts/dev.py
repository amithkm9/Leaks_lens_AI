import os
import signal
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
env = {**os.environ, "PATH": str(root / ".data/bin") + os.pathsep + os.environ["PATH"]}
processes = [
    subprocess.Popen(
        [
            str(root / "backend/.venv/bin/uvicorn"),
            "app.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--no-access-log",
        ],
        cwd=root / "backend",
        env=env,
    ),
    subprocess.Popen(["npm", "run", "dev"], cwd=root / "frontend", env=env),
]


def stop(*args):
    for process in processes:
        process.terminate()


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    processes[0].wait()
finally:
    stop()
    for process in processes:
        process.wait()
