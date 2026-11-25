from app.rag.embeddings import E5Embedder
from app.rag.ranking import metadata_text


def test_metadata_cache_reuses_heading_but_tracks_text_changes():
    embedder = object.__new__(E5Embedder)
    calls = []

    def passages(texts):
        calls.extend(texts)
        return [[1.0] + [0.0] * 383 for _ in texts]

    embedder.passages = passages
    heading = metadata_text("Source", "Feeding | PDF pages 3; line 2; part 1")
    assert heading == "Source. Feeding"
    assert embedder.metadata(heading) == embedder.metadata(heading)
    assert calls == [heading]
    embedder.metadata("Changed source. Feeding")
    assert len(calls) == 2
    embedder.metadata.cache_clear()
