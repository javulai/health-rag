import pytest
from sqlalchemy import select

from app.modules.auth import google, local
from app.modules.auth.models import User
from tests.unit.test_chat import HEADERS
from tests.unit.test_chat import client as auth_client

client = auth_client


def test_register_login_duplicate_validation_csrf(client):
    body = {"username": "new.user", "password": "long-password-123"}
    assert client.post("/api/auth/register", json=body).status_code == 403
    assert (
        client.post(
            "/api/auth/register", json={**body, "password": "short"}, headers=HEADERS
        ).status_code
        == 422
    )
    result = client.post("/api/auth/register", json=body, headers=HEADERS)
    assert result.status_code == 201
    assert client.get("/api/auth/me").json()["username"] == "new.user"
    with local.session_factory()() as session:
        user = session.scalar(select(User).where(User.username == "new.user"))
        assert user.password_hash != body["password"]
        assert local.verify_password(body["password"], user.password_hash)
    assert client.post("/api/auth/register", json=body, headers=HEADERS).status_code == 409
    client.post("/api/auth/logout", json={}, headers=HEADERS)
    assert client.post("/api/auth/login", json=body, headers=HEADERS).status_code == 200


@pytest.fixture
def google_client(client, monkeypatch):
    settings = local.get_settings()
    settings.google_client_id = "test.apps.googleusercontent.com"
    monkeypatch.setattr(google, "get_settings", lambda: settings)
    return client


def claims_for(client):
    config = client.get("/api/auth/google/config").json()
    return {
        "sub": "stable-google-id",
        "email": "thesis@example.org",
        "email_verified": True,
        "nonce": config["nonce"],
    }


def test_google_register_repeat_disabled_and_no_email_link(google_client, monkeypatch):
    client = google_client
    claims = claims_for(client)
    monkeypatch.setattr(google, "verify_token", lambda token, audience: claims)
    body = {"credential": "mock-valid-token"}
    assert client.post("/api/auth/google/login", json=body).status_code == 403
    response = client.post("/api/auth/google/login", json=body, headers=HEADERS)
    assert response.status_code == 200
    username = response.json()["username"]
    assert username != "thesis"
    assert client.get("/api/auth/me").json()["username"] == username
    assert client.post("/api/auth/google/login", json=body, headers=HEADERS).status_code == 401
    claims.update(claims_for(client))
    assert (
        client.post("/api/auth/google/login", json=body, headers=HEADERS).json()["username"]
        == username
    )
    with local.session_factory().begin() as session:
        users = session.scalars(select(User).where(User.google_sub == claims["sub"])).all()
        assert len(users) == 1
        users[0].enabled = False
    claims.update(claims_for(client))
    assert client.post("/api/auth/google/login", json=body, headers=HEADERS).status_code == 403


def test_google_wrong_nonce_and_bad_token(google_client, monkeypatch):
    client = google_client
    claims = claims_for(client)
    claims["nonce"] = "wrong"
    monkeypatch.setattr(google, "verify_token", lambda token, audience: claims)
    body = {"credential": "mock"}
    assert client.post("/api/auth/google/login", json=body, headers=HEADERS).status_code == 401

    def invalid(*args):
        raise ValueError("invalid signature/audience/expiry")

    monkeypatch.setattr(google, "verify_token", invalid)
    assert client.post("/api/auth/google/login", json=body, headers=HEADERS).status_code == 401
