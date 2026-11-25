import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.modules.auth import local
from app.rag.generation import FALLBACK, GroundedAnswer, validate_answer


@pytest.fixture
def client(monkeypatch):
    settings = Settings(
        _env_file=None, login_password_hash=local.password_hash("test-password-123")
    )
    import importlib

    monkeypatch.setattr(local, "get_settings", lambda: settings)
    monkeypatch.setattr(importlib.import_module("app.api.chat"), "get_settings", lambda: settings)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.modules.auth import history
    from app.modules.auth.models import AuthSession, Conversation, Message, User

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for model in [User, AuthSession, Conversation, Message]:
        model.__table__.create(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        session.add(User(username="thesis", password_hash=settings.login_password_hash))
    monkeypatch.setattr(local, "session_factory", lambda: factory)
    monkeypatch.setattr(history, "session_factory", lambda: factory)
    local.attempts.clear()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

    local.attempts.clear()
    engine.dispose()


HEADERS = {"X-Requested-With": "thesis-ui", "Origin": "http://localhost:3000"}


def test_auth_csrf_logout_and_unauthenticated_chat(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/chat", json={"question": "test"}, headers=HEADERS).status_code == 401
    body = {"username": "thesis", "password": "test-password-123"}
    assert client.post("/api/auth/login", json=body).status_code == 403
    assert (
        client.post(
            "/api/auth/login", json=body, headers={**HEADERS, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/login", json={**body, "password": "wrong"}, headers=HEADERS
        ).status_code
        == 401
    )
    response = client.post("/api/auth/login", json=body, headers=HEADERS)
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    token = client.cookies.get(local.COOKIE)
    assert client.get("/api/auth/me").json() == {"username": "thesis"}
    assert client.post("/api/chat", json={"question": "test"}, headers=HEADERS).status_code == 503
    client.post("/api/auth/logout", json={}, headers=HEADERS)
    client.cookies.set(local.COOKIE, token)
    assert client.get("/api/auth/me").status_code == 401


def test_login_rate_limit(client):
    for _ in range(10):
        assert (
            client.post(
                "/api/auth/login", json={"username": "thesis", "password": "bad"}, headers=HEADERS
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"username": "thesis", "password": "bad"}, headers=HEADERS
        ).status_code
        == 429
    )


def test_citation_validation_and_abstention():
    sources = [{"title": "WHO", "source_url": "https://who.int", "locator": "p1"}]
    good = GroundedAnswer(answer="Хариулт [1]", supported=True, citation_ids=[1])
    assert validate_answer(good, sources)["sources"][0]["citation_id"] == 1
    for answer, ids in [("Хариулт [2]", [2]), ("Хариулт", [1]), ("Хариулт [1]", [])]:
        with pytest.raises(ValueError):
            validate_answer(
                GroundedAnswer(answer=answer, supported=True, citation_ids=ids), sources
            )
    assert validate_answer(
        GroundedAnswer(answer="unknown", supported=False, citation_ids=[]), sources
    ) == {"answer": FALLBACK, "sources": []}


def test_expired_session(client):
    import hashlib

    from sqlalchemy import select

    from app.modules.auth.models import AuthSession, User

    with local.session_factory().begin() as session:
        user = session.scalar(select(User))
        session.add(
            AuthSession(
                token_hash=hashlib.sha256(b"expired").hexdigest(), user_id=user.id, expires_at=0
            )
        )
    client.cookies.set(local.COOKIE, "expired")
    assert client.get("/api/auth/me").status_code == 401


def test_responses_request_and_citations(monkeypatch):
    import httpx

    from app.rag import generation

    seen = {}
    real_client = httpx.Client

    def handler(request):
        import json

        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "sentences": [
                                            {"text": "Тестийн хариулт", "citation_ids": [1]}
                                        ],
                                        "supported": True,
                                        "urgent": False,
                                    }
                                ),
                            }
                        ]
                    }
                ],
            },
        )

    monkeypatch.setattr(
        generation.httpx,
        "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler)),
    )
    result = generation.generate(
        Settings(_env_file=None, openai_api_key="test-only"),
        "Асуулт",
        [
            {
                "text": "Evidence",
                "title": "WHO",
                "locator": "page 1",
                "source_url": "https://www.who.int/",
            }
        ],
    )
    assert result["answer"] == "Тестийн хариулт [1]"
    assert seen["store"] is False
    assert seen["text"]["format"]["strict"] is True
    schema = seen["text"]["format"]["schema"]
    assert set(schema["required"]) == set(schema["properties"])
    assert "default" not in schema["properties"]["urgent"]
    assert "Evidence" in seen["input"]


def test_chat_route_success_with_test_doubles(client, monkeypatch):
    import importlib

    module = importlib.import_module("app.api.chat")
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(_env_file=None, openai_api_key="test-only")
    )
    monkeypatch.setattr(module, "embedder", lambda: None)
    monkeypatch.setattr(module, "search", lambda *args: [{"text": "test-only"}])
    monkeypatch.setattr(module, "generate", lambda *args: {"answer": "Тест", "sources": []})
    client.post(
        "/api/auth/login",
        json={"username": "thesis", "password": "test-password-123"},
        headers=HEADERS,
    )
    r = client.post("/api/chat", json={"question": "Асуулт"}, headers=HEADERS)
    assert r.status_code == 200 and r.json()["answer"] == "Тест"
    assert r.headers["Cache-Control"] == "no-store"


def test_owned_history_persistence_and_idempotency(client, monkeypatch):
    import importlib
    from uuid import uuid4

    from app.modules.auth.models import User

    with local.session_factory().begin() as session:
        session.add(
            User(username="second", password_hash=local.password_hash("second-password-123"))
        )
    module = importlib.import_module("app.api.chat")
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(_env_file=None, openai_api_key="test-only")
    )
    monkeypatch.setattr(module, "embedder", lambda: None)
    monkeypatch.setattr(module, "search", lambda *a: [])
    calls = []

    def generate(*args):
        calls.append(1)
        return {"answer": "Хадгалсан хариулт", "sources": []}

    monkeypatch.setattr(module, "generate", generate)
    client.post(
        "/api/auth/login",
        json={"username": "thesis", "password": "test-password-123"},
        headers=HEADERS,
    )
    body = {"question": "Тест асуулт", "request_id": str(uuid4())}
    result = client.post("/api/chat", json=body, headers=HEADERS).json()
    cid = result["conversation_id"]
    assert client.post("/api/chat", json=body, headers=HEADERS).json() == result
    assert len(calls) == 1
    assert (
        client.post("/api/chat", json={**body, "question": "changed"}, headers=HEADERS).status_code
        == 409
    )
    client.post("/api/auth/logout", json={}, headers=HEADERS)
    client.post(
        "/api/auth/login",
        json={"username": "thesis", "password": "test-password-123"},
        headers=HEADERS,
    )
    assert len(client.get(f"/api/conversations/{cid}").json()["messages"]) == 2
    assert client.get("/api/conversations").json()[0]["id"] == cid
    client.post("/api/auth/logout", json={}, headers=HEADERS)
    client.post(
        "/api/auth/login",
        json={"username": "second", "password": "second-password-123"},
        headers=HEADERS,
    )
    assert client.get("/api/conversations").json() == []
    assert client.get(f"/api/conversations/{cid}").status_code == 404
    assert (
        client.post(
            "/api/chat", json={"question": "steal", "conversation_id": cid}, headers=HEADERS
        ).status_code
        == 404
    )
    assert client.post("/api/chat", json=body, headers=HEADERS).status_code == 404
    assert len(calls) == 1


def test_urgent_response_is_not_replaced_with_generic_abstention():
    from app.rag.generation import URGENT

    value = GroundedAnswer(answer="urgent", supported=False, citation_ids=[], urgent=True)
    assert validate_answer(value, []) == {"answer": URGENT, "sources": []}


def test_grouped_citations_normalize_without_inventing_ids():
    sources = [{"title": "one"}, {"title": "two"}]
    value = GroundedAnswer(answer="Текст [1, 2]", supported=True, citation_ids=[1, 2])
    assert validate_answer(value, sources)["answer"] == "Текст [1][2]"
    with pytest.raises(ValueError):
        validate_answer(
            GroundedAnswer(answer="Текст [1, 9]", supported=True, citation_ids=[1, 9]), sources
        )


def test_reviewer_can_reject_supported_draft(monkeypatch):
    import json

    import httpx

    from app.rag import generation

    calls = []
    real_client = httpx.Client

    def handler(request):
        calls.append(json.loads(request.content))
        value = {
            "supported": len(calls) == 1,
            "urgent": False,
            "sentences": [{"text": "Текст", "citation_ids": [1]}] if len(calls) == 1 else [],
        }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"content": [{"type": "output_text", "text": json.dumps(value)}]}],
            },
        )

    monkeypatch.setattr(
        generation.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler))
    )
    assert (
        generation.generate(
            Settings(_env_file=None, openai_api_key="test"),
            "question",
            [{"text": "text", "title": "title", "locator": "page"}],
        )["answer"]
        == FALLBACK
    )
    assert len(calls) == 2
    assert "draft" in json.loads(calls[1]["input"])


def test_sentences_require_their_own_evidence():
    from app.rag.generation import EvidenceSentence, StructuredAnswer

    with pytest.raises(ValueError):
        StructuredAnswer(
            supported=True,
            urgent=False,
            sentences=[EvidenceSentence(text="uncited claim", citation_ids=[])],
        ).rendered()
    value = StructuredAnswer(
        supported=True,
        urgent=False,
        sentences=[
            EvidenceSentence(text="Нэгдүгээр баримт", citation_ids=[1]),
            EvidenceSentence(text="Хоёрдугаар баримт", citation_ids=[2]),
        ],
    ).rendered()
    assert value.answer == "Нэгдүгээр баримт [1]\nХоёрдугаар баримт [2]"
    with pytest.raises(ValueError):
        validate_answer(value, [{"title": "only one source"}])
