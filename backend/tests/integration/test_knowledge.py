import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.modules.knowledge.models import Chunk, DocumentVersion, Source
from app.modules.knowledge.service import SourceMetadata, activate, ingest
from app.rag.retrieval import search

pytestmark = pytest.mark.integration


@pytest.fixture
def factory(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable database ending in _test")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Refusing to reset a database whose name does not end in _test")
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE chunks, document_versions, sources CASCADE"))
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()
    get_settings.cache_clear()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None, raw_data_dir=tmp_path / "archive", chunk_tokens=20, chunk_overlap=2
    )


def stage(factory, settings, embedder, tmp_path, content="alpha document", suffix="a"):
    path = tmp_path / f"{suffix}.txt"
    path.write_text(content)
    meta = SourceMetadata(
        url=f"https://example.org/{suffix}",
        title=suffix,
        organization="synthetic",
        topic="test",
        reuse_note="test",
    )
    return ingest(factory, settings, embedder, path, meta)


def test_staging_review_activation_and_disabled_filter(factory, settings, fake_embedder, tmp_path):
    from uuid import UUID

    staged = stage(factory, settings, fake_embedder, tmp_path)
    assert search(factory, fake_embedder, "alpha") == []
    activate(factory, UUID(staged["version_id"]), "test-reviewer")
    results = search(factory, fake_embedder, "alpha")
    assert len(results) == 1
    assert results[0]["source_url"] == "https://example.org/a"
    assert results[0]["locator"] == "document; line 1; part 1"
    with factory.begin() as session:
        session.scalar(select(Source)).enabled = False
    assert search(factory, fake_embedder, "alpha") == []


def test_idempotency_and_version_retirement(factory, settings, fake_embedder, tmp_path):
    from uuid import UUID

    first = stage(factory, settings, fake_embedder, tmp_path)
    duplicate = stage(factory, settings, fake_embedder, tmp_path)
    assert first["version_id"] == duplicate["version_id"]
    assert duplicate["reused"]
    activate(factory, UUID(first["version_id"]), "reviewer")
    second = stage(factory, settings, fake_embedder, tmp_path, content="beta new document")
    assert search(factory, fake_embedder, "alpha")[0]["version_id"] == first["version_id"]
    activate(factory, UUID(second["version_id"]), "reviewer")
    assert search(factory, fake_embedder, "beta")[0]["version_id"] == second["version_id"]
    with factory() as session:
        assert session.get(DocumentVersion, UUID(first["version_id"])).status == "retired"
        assert session.scalar(select(func.count()).select_from(Chunk)) == 2
    with pytest.raises(ValueError, match="staging"):
        activate(factory, UUID(first["version_id"]), "reviewer")


def test_embedding_failure_keeps_old_active(factory, settings, fake_embedder, tmp_path):
    from uuid import UUID

    first = stage(factory, settings, fake_embedder, tmp_path)
    activate(factory, UUID(first["version_id"]), "reviewer")
    original = fake_embedder.passages
    fake_embedder.passages = lambda texts: [[0.0] * 384 for _ in texts]
    with pytest.raises(ValueError):
        stage(factory, settings, fake_embedder, tmp_path, content="changed")
    fake_embedder.passages = original
    assert search(factory, fake_embedder, "alpha")[0]["version_id"] == first["version_id"]


def test_revision_mismatch_rejected(factory, settings, fake_embedder, tmp_path):
    from uuid import UUID

    first = stage(factory, settings, fake_embedder, tmp_path)
    activate(factory, UUID(first["version_id"]), "reviewer")
    fake_embedder.identity = "test-only@other-revision"
    with pytest.raises(ValueError, match="revision"):
        search(factory, fake_embedder, "alpha")
    second = stage(factory, settings, fake_embedder, tmp_path, suffix="b")
    with pytest.raises(ValueError, match="revision"):
        activate(factory, UUID(second["version_id"]), "reviewer")


def test_concurrent_ingest_is_idempotent(factory, settings, fake_embedder, tmp_path):
    path = tmp_path / "concurrent.txt"
    path.write_text("alpha concurrent")
    meta = SourceMetadata(
        url="https://example.org/concurrent",
        title="Concurrent",
        organization="test",
        topic="test",
        reuse_note="test",
    )

    def run(_):
        return ingest(factory, settings, fake_embedder, path, meta)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results[0]["version_id"] == results[1]["version_id"]


def test_incomplete_version_cannot_activate(factory, settings, fake_embedder, tmp_path):
    from uuid import UUID

    result = stage(factory, settings, fake_embedder, tmp_path)
    with factory.begin() as session:
        session.scalar(select(Chunk)).embedding = None
    with pytest.raises(ValueError, match="Every chunk"):
        activate(factory, UUID(result["version_id"]), "reviewer")


def test_migration_matches_models(factory):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.modules.knowledge.models import Base

    with factory().bind.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_metadata_reranks_candidates_and_zero_weight_restores_baseline(
    factory, settings, fake_embedder, tmp_path
):
    from uuid import UUID

    first = stage(factory, settings, fake_embedder, tmp_path, suffix="first")
    second = stage(factory, settings, fake_embedder, tmp_path, suffix="second")
    activate(factory, UUID(first["version_id"]), "test")
    activate(factory, UUID(second["version_id"]), "test")
    with factory.begin() as session:
        chunk = session.scalar(
            select(Chunk).where(Chunk.document_version_id == UUID(second["version_id"]))
        )
        chunk.embedding = [0.8, 0.6] + [0.0] * 382
    calls = []

    def metadata(value):
        calls.append(value)
        return ([1.0, 0.0] if value.startswith("second") else [0.0, 1.0]) + [0.0] * 382

    fake_embedder.metadata = metadata
    baseline = search(factory, fake_embedder, "alpha", 1, metadata_weight=0)
    assert baseline[0]["version_id"] == first["version_id"]
    assert calls == []
    ranked = search(factory, fake_embedder, "alpha", 1, metadata_weight=0.3)
    assert ranked[0]["version_id"] == second["version_id"]
    assert len(calls) == 2  # Fetch beyond the final top-1 before reranking.
    assert ranked[0]["score"] == pytest.approx(0.86)
    with factory.begin() as session:
        session.scalar(select(Source).where(Source.title == "second")).enabled = False
    calls.clear()
    assert search(factory, fake_embedder, "alpha", 1)[0]["version_id"] == first["version_id"]
    assert all(not value.startswith("second") for value in calls)


def test_chat_history_survives_new_connection_and_enforces_owner(factory, monkeypatch):
    from uuid import UUID, uuid4

    from fastapi import HTTPException
    from sqlalchemy import delete

    from app.modules.auth import history
    from app.modules.auth.models import User

    name = f"test-{uuid4()}"
    other = f"other-{uuid4()}"
    with factory.begin() as session:
        session.add_all(
            [User(username=name, password_hash="test"), User(username=other, password_hash="test")]
        )
    monkeypatch.setattr(history, "session_factory", lambda: factory)
    request_id = uuid4()
    try:
        saved = history.save_turn(
            name,
            None,
            request_id,
            "question",
            {"answer": "answer", "sources": [{"citation_id": 1, "title": "snapshot"}]},
        )
        factory.kw["bind"].dispose()
        assert history.previous(name, None, request_id, "question") == saved
        with pytest.raises(HTTPException) as caught:
            history.previous(other, UUID(saved["conversation_id"]), uuid4(), "question")
        assert caught.value.status_code == 404
    finally:
        with factory.begin() as session:
            session.execute(delete(User).where(User.username.in_([name, other])))
