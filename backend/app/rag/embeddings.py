"""Local E5 baseline. Test doubles live only in tests, never in the production factory."""

import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.core.config import Settings
from app.modules.knowledge.models import DIMENSION


class E5Embedder:
    def __init__(self, settings: Settings):
        if settings.embedding_model != "intfloat/multilingual-e5-small":
            raise ValueError("This baseline supports multilingual-e5-small only (384 dimensions)")
        try:
            from huggingface_hub import hf_hub_download
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ValueError("Install embeddings first: uv sync --extra embedding") from exc
        config_path = hf_hub_download(
            settings.embedding_model,
            "config.json",
            revision=settings.embedding_revision,
            cache_dir=str(settings.hf_home),
        )
        revision = Path(config_path).parent.name
        if not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Cannot resolve model revision from the model snapshot")
        self.model = SentenceTransformer(
            settings.embedding_model,
            revision=revision,
            cache_folder=str(settings.hf_home),
            device="cpu",
            trust_remote_code=False,
        )
        self.tokenizer = self.model.tokenizer
        self.identity = f"{settings.embedding_model}@{revision}"
        if self.model.get_sentence_embedding_dimension() != DIMENSION:
            raise ValueError("Embedding dimension does not match the database schema")
        prefix_tokens = len(self.tokenizer("passage: ")["input_ids"])
        if settings.chunk_tokens + prefix_tokens > self.model.max_seq_length:
            raise ValueError("Chunk size exceeds the model context limit")

    def _encode(self, texts: list[str], prefix: str) -> list[list[float]]:
        prefixed = [prefix + text for text in texts]
        if any(
            len(self.tokenizer(text)["input_ids"]) > self.model.max_seq_length for text in prefixed
        ):
            raise ValueError("Text exceeds the embedding context; shorten the query/chunks")
        vectors = self.model.encode(
            prefixed, batch_size=16, normalize_embeddings=True, show_progress_bar=False
        )
        return validate_vectors(vectors, len(texts))

    def passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, "passage: ")

    @lru_cache(maxsize=2048)
    def metadata(self, text: str) -> tuple[float, ...]:
        return tuple(self.passages([text])[0])

    def query(self, text: str) -> list[float]:
        return self._encode([text], "query: ")[0]


def validate_vectors(vectors, expected_count: int) -> list[list[float]]:
    values = np.asarray(vectors, dtype=float)
    if values.shape != (expected_count, DIMENSION):
        raise ValueError("Embedding count or dimension mismatch")
    if not np.isfinite(values).all() or (np.linalg.norm(values, axis=1) == 0).any():
        raise ValueError("Embeddings must be finite, nonzero vectors")
    return values.tolist()
