import json
import time
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.rag.retrieval import search


def evaluate(factory, embedder, dataset: Path, limit: int = 5) -> dict:
    cases = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    if not cases:
        raise ValueError("Evaluation dataset is empty")
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation IDs must be unique")
    rows = []
    for case in cases:
        expected = {(item["url"], item["locator"]) for item in case["relevant"]}
        if not expected:
            raise ValueError("This retrieval evaluation requires a relevant chunk for every case")
        started = time.monotonic()
        results = search(factory, embedder, case["question"], limit)
        found = {(item["source_url"], item["locator"]) for item in results}
        rows.append(
            {
                "id": case["id"],
                "split": case["split"],
                "recall": len(expected & found) / len(expected),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "retrieved_chunk_ids": [item["chunk_id"] for item in results],
            }
        )
    return {
        "summary": {
            "cases": len(rows),
            f"recall_at_{limit}": sum(row["recall"] for row in rows) / len(rows),
            "model": embedder.identity,
            "timestamp": datetime.now(UTC).isoformat(),
            "dataset": str(dataset),
            "scope": "retrieval_only",
            "metadata_weight": get_settings().retrieval_metadata_weight,
            "candidate_limit": get_settings().retrieval_candidates,
        },
        "rows": rows,
    }
