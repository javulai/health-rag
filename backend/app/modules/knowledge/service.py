import hashlib
import os
import tempfile
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from app.core.config import Settings
from app.modules.knowledge.models import Chunk, DocumentVersion, Source
from app.rag.documents import chunk_sections, read_sections
from app.rag.embeddings import validate_vectors


class SourceMetadata(BaseModel):
    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    organization: str = Field(min_length=1, max_length=300)
    language: str = Field(default="mn", min_length=2, max_length=16)
    topic: str = Field(min_length=1, max_length=300)
    reuse_note: str = Field(min_length=1)
    published_at: date | None = None
    updated_at: date | None = None

    @field_validator("title", "organization", "topic", "reuse_note", "language")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Value cannot be blank")
        return value.strip()

    @field_validator("url")
    @classmethod
    def https_only(cls, value):
        if value.scheme != "https":
            raise ValueError("Citation source URL must use HTTPS")
        return value


def ingest(factory, settings: Settings, embedder, path: Path, metadata: SourceMetadata) -> dict:
    # Read a single immutable snapshot so the checksum and parsed text cannot diverge.
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Document exceeds the 20 MiB prototype limit")
    payload = path.read_bytes()
    checksum = hashlib.sha256(payload).hexdigest()
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    stored = settings.raw_data_dir / f"{checksum}{path.suffix.lower()}"
    if stored.exists():
        if hashlib.sha256(stored.read_bytes()).hexdigest() != checksum:
            raise ValueError("Archived file checksum mismatch")
    else:
        # Publish a complete file atomically, including simultaneous ingestions.
        with tempfile.NamedTemporaryFile(dir=settings.raw_data_dir, delete=False) as output:
            temporary = Path(output.name)
            output.write(payload)
        try:
            try:
                os.link(temporary, stored)
            except FileExistsError:
                if hashlib.sha256(stored.read_bytes()).hexdigest() != checksum:
                    raise ValueError("Archived file checksum mismatch")
        finally:
            temporary.unlink(missing_ok=True)
    chunks = chunk_sections(
        read_sections(stored), embedder.tokenizer, settings.chunk_tokens, settings.chunk_overlap
    )
    config = {
        "tokenizer": embedder.identity,
        "token_limit": settings.chunk_tokens,
        "overlap": settings.chunk_overlap,
        "parser_version": "local-v1",
    }
    # Model execution is outside database transactions. Failures leave active versions intact.
    vectors = validate_vectors(embedder.passages([chunk.text for chunk in chunks]), len(chunks))
    with factory.begin() as session:
        session.execute(
            insert(Source)
            .values(
                canonical_url=str(metadata.url),
                title=metadata.title,
                organization=metadata.organization,
                language=metadata.language,
                topic=metadata.topic,
                reuse_note=metadata.reuse_note,
            )
            .on_conflict_do_nothing(index_elements=[Source.canonical_url])
        )
        source = session.scalar(
            select(Source).where(Source.canonical_url == str(metadata.url)).with_for_update()
        )
        existing = session.scalar(
            select(DocumentVersion)
            .where(
                DocumentVersion.source_id == source.id,
                DocumentVersion.checksum == checksum,
                DocumentVersion.embedding_model == embedder.identity,
                DocumentVersion.chunking_config == config,
                DocumentVersion.status.in_(["staging", "active", "retired"]),
            )
            .order_by(DocumentVersion.version_no.desc())
        )
        if existing:
            return {"version_id": str(existing.id), "status": existing.status, "reused": True}
        source.title, source.organization = metadata.title, metadata.organization
        source.language, source.topic = metadata.language, metadata.topic
        source.reuse_note, source.updated_at = metadata.reuse_note, datetime.now(UTC)
        number = (
            session.scalar(
                select(func.coalesce(func.max(DocumentVersion.version_no), 0)).where(
                    DocumentVersion.source_id == source.id
                )
            )
            + 1
        )
        version = DocumentVersion(
            source_id=source.id,
            version_no=number,
            checksum=checksum,
            source_published_at=metadata.published_at,
            source_updated_at=metadata.updated_at,
            file_path=str(stored.resolve()),
            status="staging",
            embedding_model=embedder.identity,
            chunking_config=config,
        )
        session.add(version)
        session.flush()
        session.add_all(
            [
                Chunk(
                    document_version_id=version.id,
                    chunk_index=i,
                    text=chunk.text,
                    locator=chunk.locator,
                    token_count=chunk.token_count,
                    language=metadata.language,
                    embedding=vector,
                )
                for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ]
        )
        return {
            "version_id": str(version.id),
            "status": "staging",
            "chunk_count": len(chunks),
            "reused": False,
        }


def inspect_version(factory, version_id: uuid.UUID) -> dict:
    with factory() as session:
        version = session.get(DocumentVersion, version_id)
        if not version:
            raise ValueError("Document version not found")
        chunks = session.scalars(
            select(Chunk).where(Chunk.document_version_id == version_id).order_by(Chunk.chunk_index)
        ).all()
        return {
            "version_id": str(version.id),
            "status": version.status,
            "model": version.embedding_model,
            "chunking_config": version.chunking_config,
            "chunks": [
                {
                    "id": str(c.id),
                    "locator": c.locator,
                    "text": c.text,
                    "token_count": c.token_count,
                }
                for c in chunks
            ],
        }


def activate(factory, version_id: uuid.UUID, reviewer: str) -> dict:
    if not reviewer.strip():
        raise ValueError("Reviewer cannot be blank")
    with factory.begin() as session:
        # Serialize activation across sources to keep a single embedding space in the corpus.
        session.execute(text("SELECT pg_advisory_xact_lock(7241301)"))
        version = session.get(DocumentVersion, version_id)
        if not version:
            raise ValueError("Document version not found")
        source = session.scalar(
            select(Source).where(Source.id == version.source_id).with_for_update()
        )
        if version.status == "active":
            return {"version_id": str(version.id), "status": "active", "reused": True}
        if version.status != "staging":
            raise ValueError("Only a reviewed staging version can be activated")
        if not source.enabled:
            raise ValueError("Source is disabled")
        incompatible = session.scalar(
            select(DocumentVersion.id)
            .where(
                DocumentVersion.status == "active",
                DocumentVersion.source_id != source.id,
                DocumentVersion.embedding_model != version.embedding_model,
            )
            .limit(1)
        )
        if incompatible:
            raise ValueError("Active corpus uses a different embedding model revision")
        count, embedded = session.execute(
            select(func.count(Chunk.id), func.count(Chunk.embedding)).where(
                Chunk.document_version_id == version.id
            )
        ).one()
        if count == 0 or count != embedded:
            raise ValueError("Every chunk needs an embedding before activation")
        session.execute(
            update(DocumentVersion)
            .where(DocumentVersion.source_id == source.id, DocumentVersion.status == "active")
            .values(status="retired")
        )
        version.status = "active"
        version.reviewed_at = version.activated_at = datetime.now(UTC)
        version.reviewer_ref = reviewer.strip()
        return {"version_id": str(version.id), "status": "active", "chunk_count": count}
