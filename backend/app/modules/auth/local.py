"""Database-backed sessions; local-process login throttling."""

import hashlib
import hmac
import secrets
import threading
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.session import session_factory
from app.modules.auth.models import AuthSession, User

router = APIRouter(prefix="/api/auth")
COOKIE = "thesis_session"
TTL = 8 * 3600

attempts: deque[float] = deque()
lock = threading.Lock()


def password_hash(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    value = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
    return f"{salt}:{value.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        salt, _ = encoded.split(":", 1)
        return hmac.compare_digest(password_hash(password, salt), encoded)
    except (ValueError, TypeError):
        return False


DUMMY_HASH = password_hash(secrets.token_urlsafe(32))


def csrf(request: Request):
    settings = get_settings()
    if request.headers.get("x-requested-with") != "thesis-ui":
        raise HTTPException(403, "Хүсэлтийн хамгаалалт дутуу байна.")
    origin = request.headers.get("origin")
    if origin and origin not in settings.frontend_origins.split(","):
        raise HTTPException(403, "Зөвшөөрөөгүй эх үүсвэр.")


def current_user(request: Request) -> str:
    token = request.cookies.get(COOKIE, "")
    key = hashlib.sha256(token.encode()).hexdigest()
    with session_factory()() as session:
        user = session.scalar(
            select(User)
            .join(AuthSession)
            .where(
                AuthSession.token_hash == key,
                AuthSession.expires_at > time.time(),
                User.enabled.is_(True),
            )
        )
        if not user:
            raise HTTPException(401, "Дахин нэвтэрнэ үү.")
        return user.username


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login", dependencies=[Depends(csrf)])
def login(body: Login, request: Request, response: Response):
    throttle()
    now = time.time()
    with session_factory().begin() as session:
        user = session.scalar(select(User).where(User.username == body.username))
        valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
        if not valid or not user or not user.enabled:
            raise HTTPException(401, "Хэрэглэгчийн нэр эсвэл нууц үг буруу байна.")
        token = create_session(session, user, request, now)
    set_session_cookie(response, token)
    return {"username": body.username}


def throttle():
    now = time.time()
    with lock:
        while attempts and attempts[0] < now - 60:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(429, "Хэт олон оролдлого. Нэг минутын дараа оролдоно уу.")
        attempts.append(now)


def create_session(session, user, request, now):
    token = secrets.token_urlsafe(32)
    old = request.cookies.get(COOKIE, "")
    session.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    session.execute(
        delete(AuthSession).where(
            AuthSession.token_hash == hashlib.sha256(old.encode()).hexdigest()
        )
    )
    session.add(
        AuthSession(
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            user_id=user.id,
            expires_at=now + TTL,
        )
    )
    return token


def set_session_cookie(response, token):
    response.set_cookie(
        COOKIE,
        token,
        max_age=TTL,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


class Register(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    password: str = Field(min_length=12, max_length=256)


@router.post("/register", dependencies=[Depends(csrf)], status_code=201)
def register(body: Register, request: Request, response: Response):
    throttle()
    if body.username.startswith("google_"):
        raise HTTPException(422, "Өөр хэрэглэгчийн нэр сонгоно уу.")
    hashed = password_hash(body.password)
    try:
        with session_factory().begin() as session:
            user = User(username=body.username, password_hash=hashed)
            session.add(user)
            session.flush()
            token = create_session(session, user, request, time.time())
    except IntegrityError:
        raise HTTPException(409, "Энэ хэрэглэгчийн нэр бүртгэлтэй байна.") from None
    set_session_cookie(response, token)
    return {"username": body.username}


@router.get("/me")
def me(response: Response, username: str = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return {"username": username}


@router.post("/logout", dependencies=[Depends(csrf)])
def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE, "")
    with session_factory().begin() as session:
        session.execute(
            delete(AuthSession).where(
                AuthSession.token_hash == hashlib.sha256(token.encode()).hexdigest()
            )
        )
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
