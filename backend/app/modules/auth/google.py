"""Google Identity Services popup: verified ID token -> local application session."""

import hmac
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.modules.auth import local
from app.modules.auth.models import User

router = APIRouter(prefix="/api/auth/google")
NONCE_COOKIE = "thesis_google_nonce"


@router.get("/config")
def config(response: Response):
    settings = get_settings()
    response.headers["Cache-Control"] = "no-store"
    if not settings.google_client_id:
        return {"enabled": False}
    nonce = secrets.token_urlsafe(32)
    response.set_cookie(
        NONCE_COOKIE,
        nonce,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {"enabled": True, "client_id": settings.google_client_id, "nonce": nonce}


class Credential(BaseModel):
    credential: str = Field(min_length=1, max_length=10000)


def verify_token(credential, audience):
    # Library validates Google signature, issuer, audience and expiration.
    transport = GoogleRequest()

    def bounded_request(*args, **kwargs):
        kwargs["timeout"] = 10
        return transport(*args, **kwargs)

    return id_token.verify_oauth2_token(credential, bounded_request, audience=audience)


@router.post("/login", dependencies=[Depends(local.csrf)])
def login(body: Credential, request: Request, response: Response):
    audience = get_settings().google_client_id
    if not audience:
        raise HTTPException(503, "Google нэвтрэлт тохируулагдаагүй байна.")
    local.throttle()
    nonce = request.cookies.get(NONCE_COOKIE, "")
    if not nonce:
        raise HTTPException(401, "Нэвтрэх хуудсыг шинэчилж дахин оролдоно уу.")
    try:
        claims = verify_token(body.credential, audience)
    except ValueError:
        raise HTTPException(401, "Google нэвтрэлтийг баталгаажуулж чадсангүй.") from None
    except GoogleAuthError:
        raise HTTPException(503, "Google үйлчилгээтэй холбогдож чадсангүй.") from None
    if (
        not isinstance(claims.get("nonce"), str)
        or not hmac.compare_digest(claims["nonce"], nonce)
        or not isinstance(claims.get("sub"), str)
        or not 1 <= len(claims["sub"]) <= 255
        or claims.get("email_verified") is not True
    ):
        raise HTTPException(401, "Google нэвтрэлтийн мэдээлэл тохирохгүй байна.")
    # Never link by email or display name: only Google's stable subject identifies the account.
    try:
        with local.session_factory().begin() as session:
            user = session.scalar(select(User).where(User.google_sub == claims["sub"]))
            if user is None:
                user = User(
                    username="google_" + secrets.token_hex(12),
                    google_sub=claims["sub"],
                    email=claims.get("email"),
                    password_hash=local.password_hash(secrets.token_urlsafe(48)),
                )
                session.add(user)
                session.flush()
            if not user.enabled:
                raise HTTPException(403, "Энэ хэрэглэгчийн эрх хаалттай байна.")
            token = local.create_session(session, user, request, time.time())
            username = user.username
    except IntegrityError:
        raise HTTPException(409, "Нэвтрэх хуудсыг шинэчилж дахин оролдоно уу.") from None
    local.set_session_cookie(response, token)
    response.delete_cookie(NONCE_COOKIE, path="/")
    return {"username": username}
