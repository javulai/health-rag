"""Run from backend/: compare frozen labels at a fixed top-k."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import get_settings  # noqa: E402
from app.db.session import session_factory  # noqa: E402
from app.rag.embeddings import E5Embedder  # noqa: E402
from app.rag.retrieval import search  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--weights", type=float, nargs="+", default=[0, 0.3])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = [
        json.loads(line)
        for line in args.dataset.read_text().splitlines()
        if line.strip()
    ]
    if not cases or any(not c["relevant"] for c in cases):
        raise ValueError("Need nonempty cases and labels")
    settings = get_settings()
    embedder = E5Embedder(settings)
    factory = session_factory()
    output = dict(
        dataset=str(args.dataset),
        dataset_sha256=hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        model=embedder.identity,
        candidates=settings.retrieval_candidates,
        top_k=5,
        variants={},
    )
    for weight in args.weights:
        records = []
        for case in cases:
            start = time.monotonic()
            results = search(
                factory, embedder, case["question"], 5, metadata_weight=weight
            )
            targets = {(x["url"], x["locator"]) for x in case["relevant"]}
            found = {(x["source_url"], x["locator"]) for x in results}
            records.append(
                dict(
                    id=case["id"],
                    recall=len(targets & found) / len(targets),
                    latency_ms=round((time.monotonic() - start) * 1000),
                    results=[
                        dict(
                            chunk_id=x["chunk_id"],
                            url=x["source_url"],
                            locator=x["locator"],
                            score=x["score"],
                        )
                        for x in results
                    ],
                )
            )
        score = sum(x["recall"] for x in records) / len(records)
        output["variants"][str(weight)] = dict(
            recall_at_5=score, cases=len(records), rows=records
        )
        print(f"weight={weight}, recall@5={score:.4f}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
