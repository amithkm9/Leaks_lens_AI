import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import Session, User, now

passwords = PasswordHash.recommended()
dummy_password_hash = passwords.hash(secrets.token_urlsafe(32))


def verify_password(password, stored_hash):
    # Missing accounts still incur the password-hashing work of an existing account.
    return passwords.verify(password, stored_hash or dummy_password_hash)


def token_hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db, user):
    token, csrf = secrets.token_urlsafe(32), secrets.token_hex(32)
    db.add(
        Session(
            user_id=user.id,
            token_hash=token_hash(token),
            csrf=csrf,
            expires_at=(datetime.now(timezone.utc) + timedelta(hours=settings().session_hours)).isoformat(),
        )
    )
    db.commit()
    return token, csrf


def current_user(request: Request, db: DBSession = Depends(get_db)):
    token = request.cookies.get("leaklens_session", "")
    session = db.scalar(
        select(Session).where(Session.token_hash == token_hash(token), Session.expires_at > now())
    )
    if not session:
        raise HTTPException(401, "Sign in to continue")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, "Session no longer valid")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if settings().public_read_only and request.url.path != "/api/auth/logout":
            raise HTTPException(403, "This workspace is read-only")
        if not secrets.compare_digest(
            request.headers.get("x-csrf-token", "").encode(), session.csrf.encode()
        ):
            raise HTTPException(403, "Refresh your session before making changes")
    request.state.session = session
    return user


def scoped(db, model, record_id, workspace_id):
    row = db.scalar(select(model).where(model.id == record_id, model.workspace_id == workspace_id))
    if row is None:
        raise HTTPException(404, "Record not found")
    return row
