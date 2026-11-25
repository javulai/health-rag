"""Load only repository-owned synthetic fixtures into a dedicated demo database."""

import json
import os
from pathlib import Path
from uuid import UUID

from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.db.session import session_factory
from app.modules.knowledge.service import SourceMetadata, activate, ingest, inspect_version
from app.rag.embeddings import E5Embedder
from app.rag.evaluation import evaluate


def main():
    settings = get_settings()
    if not (make_url(settings.database_url).database or "").endswith("_demo"):
        raise SystemExit("Use a separate DATABASE_URL ending in _demo for synthetic fixtures")
    base = Path(os.getenv("EVALUATION_DIR", "../data/evaluation"))
    root = base / "smoke"
    factory = session_factory()
    embedder = E5Embedder(settings)
    for path in sorted(root.glob("*.md")):
        metadata_file = path.with_suffix(".json")
        if not metadata_file.exists():
            continue
        metadata = SourceMetadata.model_validate_json(metadata_file.read_text())
        result = ingest(factory, settings, embedder, path, metadata)
        version_id = UUID(result["version_id"])
        inspected = inspect_version(factory, version_id)
        # These ten reviewed, repository-owned fixtures each have exactly one paragraph.
        if len(inspected["chunks"]) != 1:
            raise ValueError("Synthetic fixture chunking changed; review evaluation labels")
        activated = activate(factory, version_id, "repository-synthetic-fixture-check")
        print(json.dumps({"fixture": path.name, **result, **activated}, ensure_ascii=False))
    result = evaluate(factory, embedder, root / "questions.jsonl")
    output = base / "results" / "smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
