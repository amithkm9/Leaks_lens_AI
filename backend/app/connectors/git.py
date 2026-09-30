import os
import subprocess
from app.config import settings
from app.connectors import Collection, Item
from app.connectors.policy import local_repository, validate_url
from app.detectors import safe_text
from app.parsers import supported


def git_args(repo):
    return [
        "git",
        "--no-optional-locks",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "protocol.ext.allow=never",
        "-c",
        "submodule.recurse=false",
        "-C",
        str(repo),
    ]


def git_env():
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_ALLOW_PROTOCOL": "https",
        "GIT_NO_LAZY_FETCH": "1",
    }


def run(repo, args, max_bytes=1024 * 1024):
    with subprocess.Popen(
        git_args(repo) + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=git_env()
    ) as proc:
        # A watchdog bounds both waiting and output; repository content never executes.
        import threading

        timer = threading.Timer(25, proc.kill)
        timer.start()
        try:
            data = proc.stdout.read(max_bytes + 1)
            if len(data) > max_bytes:
                proc.kill()
                raise ValueError("Git output exceeds configured limit")
            proc.wait(timeout=3)
            if proc.returncode:
                raise ValueError("Git read failed or timed out")
            return data
        finally:
            timer.cancel()


def collect(config, staging, cancelled=lambda: False):
    result = Collection()
    history = min(config.get("history_commits", 1), settings().max_history_commits)
    if config.get("path"):
        repo = local_repository(config["path"])
    else:
        url = config["url"]
        p, ips = validate_url(url, config)
        if p.scheme != "https":
            raise ValueError("Remote Git requires HTTPS")
        repo = staging / "repository"
        # Disable redirects and pin libcurl DNS to the validated destination.
        args = [
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "http.followRedirects=false",
            "-c",
            f"http.curloptResolve={p.hostname}:{p.port or 443}:{ips[0]}",
            "clone",
            "--no-checkout",
            "--no-recurse-submodules",
            "--single-branch",
            f"--depth={history}",
            "--",
            url,
            str(repo),
        ]
        try:
            proc = subprocess.run(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90, env=git_env()
            )
        except subprocess.TimeoutExpired:
            raise ValueError("Remote Git fetch timed out") from None
        if proc.returncode:
            raise ValueError("Remote Git fetch failed; verify authorization, reachability, and Git version")
    commits = run(repo, ["rev-list", f"--max-count={history}", "HEAD"]).decode().splitlines()
    for ci, commit in enumerate(commits):
        tree = run(repo, ["ls-tree", "-r", "-z", commit])
        for entry in tree.split(b"\x00"):
            if not entry:
                continue
            if cancelled():
                result.complete = False
                result.warnings.append("Collection cancelled")
                return result
            info, raw_name = entry.split(b"\t", 1)
            mode, kind, obj = info.decode().split()
            name = raw_name.decode("utf-8", errors="replace")
            if mode == "120000" or kind != "blob":
                result.warnings.append(f"Symlink or submodule skipped: {safe_text(name)}")
                result.complete = False
                continue
            if not supported(name):
                result.warnings.append(f"Unsupported file skipped: {safe_text(name)}")
                result.complete = False
                continue
            if len(result.items) >= min(config.get("max_documents", 100), settings().max_documents):
                result.complete = False
                result.warnings.append("Git document limit reached; history is only partially scanned")
                return result
            try:
                size = int(run(repo, ["cat-file", "-s", obj], 100))
                if size > settings().max_file_bytes:
                    raise ValueError("File exceeds byte limit")
                data = run(repo, ["cat-file", "blob", obj], settings().max_file_bytes)
                path = staging / f"blob-{len(result.items)}"
                path.write_bytes(data)
                result.items.append(Item(path, name, name, "current" if ci == 0 else commit))
            except ValueError as exc:
                result.errors.append(f"{safe_text(name)}: {exc}")
                result.complete = False
    result.checkpoint = {
        "head": commits[0] if commits else None,
        "commits_scanned": len(commits),
        "history_limit": history,
    }
    return result
