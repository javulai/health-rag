import re

import pytest

from app.modules.knowledge.models import DIMENSION


class WordTokenizer:
    def __call__(self, value, **kwargs):
        matches = list(re.finditer(r"\S+", value))
        return {
            "input_ids": list(range(len(matches))),
            "offset_mapping": [(m.start(), m.end()) for m in matches],
        }


class FakeEmbedder:
    """Only checks plumbing. Never evidence of semantic retrieval quality."""

    identity = "test-only@fixed"
    tokenizer = WordTokenizer()

    def passages(self, texts):
        return [self.query(text) for text in texts]

    def query(self, text):
        v = [0.0] * DIMENSION
        v[0 if "alpha" in text.lower() else 1] = 1.0
        return v


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()
