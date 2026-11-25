import numpy as np
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.knowledge.models import Chunk, DocumentVersion, Source
from app.rag.embeddings import validate_vectors
from app.rag.ranking import blend_score, metadata_text


def search(factory, embedder, question: str, limit: int = 5, *, metadata_weight=None) -> list[dict]:
    if not question.strip():
        raise ValueError("Question cannot be blank")
    if not 1 <= limit <= 20:
        raise ValueError("Limit must be between 1 and 20")
    settings = get_settings()
    weight = settings.retrieval_metadata_weight if metadata_weight is None else metadata_weight
    if not 0 <= weight <= 1:
        raise ValueError("Metadata weight must be between 0 and 1")
    vector = validate_vectors([embedder.query(question)], 1)[0]
    with factory() as session:
        # Fail visibly instead of silently dropping sources indexed with another revision.
        models = session.scalars(
            select(DocumentVersion.embedding_model)
            .join(Source)
            .where(DocumentVersion.status == "active", Source.enabled.is_(True))
            .distinct()
        ).all()
        if any(model != embedder.identity for model in models):
            raise ValueError("Query model revision differs from the active corpus; reindex first")
        distance = Chunk.embedding.cosine_distance(vector).label("distance")
        rows = session.execute(
            select(Chunk, Source, DocumentVersion, distance)
            .join(DocumentVersion, Chunk.document_version_id == DocumentVersion.id)
            .join(Source, DocumentVersion.source_id == Source.id)
            .where(
                Source.enabled.is_(True),
                DocumentVersion.status == "active",
                Chunk.embedding.is_not(None),
            )
            .order_by(distance, Chunk.id)
            .limit(settings.retrieval_candidates if weight else limit)
        ).all()
    ranked = []
    query_vector = np.asarray(vector)
    query_norm = np.linalg.norm(query_vector)
    for c, source, version, dist in rows:
        content_score = 1 - float(dist)
        score = content_score
        if weight:
            heading = metadata_text(source.title, c.locator)
            values = (
                embedder.metadata(heading)
                if hasattr(embedder, "metadata")
                else embedder.passages([heading])[0]
            )
            v = np.asarray(validate_vectors([values], 1)[0])
            heading_score = float(np.dot(query_vector, v) / (query_norm * np.linalg.norm(v)))
            score = blend_score(content_score, heading_score, weight)
        ranked.append((c, source, version, score))
    ranked.sort(key=lambda row: (-row[3], str(row[0].id)))
    return [
        {
            "chunk_id": str(c.id),
            "version_id": str(v.id),
            "text": c.text,
            "locator": c.locator,
            "source_url": s.canonical_url,
            "title": s.title,
            "organization": s.organization,
            "source_date": str(v.source_updated_at or v.source_published_at)
            if v.source_updated_at or v.source_published_at
            else None,
            "score": round(score, 6),
        }
        for c, s, v, score in ranked[:limit]
    ]
