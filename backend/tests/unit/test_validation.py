import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.main import app
from app.modules.knowledge.service import SourceMetadata
from app.rag.embeddings import validate_vectors


def test_no_zero_nan_or_wrong_size_vectors():
    for vectors in ([[0] * 384], [[float("nan")] * 384], [[1, 2]], []):
        with pytest.raises(ValueError):
            validate_vectors(vectors, 1)


def test_metadata_https_and_nonblank():
    data = dict(
        url="http://example.org/doc",
        title="title",
        organization="org",
        topic="topic",
        reuse_note="test",
    )
    with pytest.raises(ValidationError):
        SourceMetadata(**data)
    data.update(url="https://example.org/doc", title="   ")
    with pytest.raises(ValidationError):
        SourceMetadata(**data)


def test_overlap_config():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, chunk_tokens=20, chunk_overlap=20)


def test_liveness_does_not_need_database():
    assert TestClient(app).get("/health").json() == {"status": "ok"}


def test_readiness_failure_does_not_leak_credentials(monkeypatch):
    def broken():
        raise OperationalError("secret-password", {}, Exception("private"))

    monkeypatch.setattr("app.main.get_engine", broken)
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
