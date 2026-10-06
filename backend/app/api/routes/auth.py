import time
from collections import OrderedDict, deque
from threading import Lock
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession
from app.config import settings
from app.db import get_db
from app.models import (
    User,
    Session,
)
from app.security import current_user, verify_password, create_session
from app.api.schemas import (
    LoginIn,
)

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["auth"])
login_attempts = OrderedDict()
login_attempts_lock = Lock()


def throttle_login(identity):
    now_seconds = time.monotonic()
    with login_attempts_lock:
        while login_attempts:
            first = next(iter(login_attempts))
            if login_attempts[first][-1] >= now_seconds - 60:
                break
            login_attempts.popitem(last=False)
        if identity not in login_attempts:
            if len(login_attempts) >= 4096:
                raise HTTPException(429, "Too many sign-in attempts; wait one minute")
            login_attempts[identity] = deque()
        attempts = login_attempts[identity]
        while attempts and attempts[0] < now_seconds - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many sign-in attempts; wait one minute")
        attempts.append(now_seconds)
        login_attempts.move_to_end(identity)


@router.post("/auth/login")
def login(payload: LoginIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    identity = request.client.host if request.client else "unknown"
    throttle_login(identity)
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    valid = verify_password(payload.password, user.password_hash if user else None)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect")
    token, csrf = create_session(db, user)
    response.set_cookie(
        "leaklens_session",
        token,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        max_age=settings().session_hours * 3600,
        path="/",
    )
    return {"email": user.email, "csrf_token": csrf}


@router.get("/auth/me")
def me(request: Request, user=Depends(current_user)):
    return {
        "email": user.email,
        "csrf_token": request.state.session.csrf,
        "read_only": settings().public_read_only,
    }


@router.post("/auth/logout")
def logout(request: Request, response: Response, user=Depends(current_user), db: DBSession = Depends(get_db)):
    db.delete(db.get(Session, request.state.session.id))
    db.commit()
    response.delete_cookie("leaklens_session", path="/")
    return {"ok": True}
