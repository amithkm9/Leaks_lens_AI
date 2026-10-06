import argparse
import getpass
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Investigation, ScanJob, User, Workspace, now
from app.security import passwords


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-user", "recover-jobs", "purge-raw"])
    parser.add_argument("--email")
    parser.add_argument("--workspace", default="My workspace")
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.command == "create-user":
            email = args.email or input("Analyst email: ").strip()
            password = os.environ.get("LEAKLENS_SETUP_PASSWORD") or getpass.getpass(
                "Analyst password (at least 12 characters): "
            )
            if len(password) < 12:
                raise SystemExit("Choose a password of at least 12 characters")
            if db.scalar(select(User).where(User.email == email.lower())):
                raise SystemExit("User already exists; no credentials changed")
            workspace = db.scalar(select(Workspace).where(Workspace.name == args.workspace))
            if workspace is None:
                workspace = Workspace(name=args.workspace)
                db.add(workspace)
                db.flush()
            db.add(
                User(workspace_id=workspace.id, email=email.lower(), password_hash=passwords.hash(password))
            )
            db.commit()
            print("Analyst created. No demonstration data was added.")
        elif args.command == "recover-jobs":
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()
            count = 0
            for job in db.scalars(
                select(ScanJob).where(ScanJob.status.in_(["queued", "running"]), ScanJob.created_at < cutoff)
            ):
                if job.heartbeat_at and job.heartbeat_at >= cutoff:
                    continue
                job.status = "failed"
                job.errors = ["Worker interrupted or queue expired. Retry this scan to resume idempotently."]
                job.finished_at = now()
                count += 1
            for run in db.scalars(
                select(Investigation).where(
                    Investigation.status.in_(["queued", "running"]), Investigation.created_at < cutoff
                )
            ):
                run.status = "failed"
                run.error = "Worker interrupted; start a new investigation"
                count += 1
            db.commit()
            print(f"Recovered {count} stale jobs")
        else:
            from app.workers.jobs import purge_raw

            print(f"Removed {purge_raw()} expired raw files/directories")


if __name__ == "__main__":
    main()
