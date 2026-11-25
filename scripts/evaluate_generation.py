"""Run from backend/. Sends fixed nonpersonal questions and retrieved evidence to OpenAI."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import get_settings
from app.db.session import session_factory
from app.rag.embeddings import E5Embedder
from app.rag.generation import (
    FALLBACK,
    INSTRUCTIONS,
    PROMPT_VERSION,
    REVIEW_INSTRUCTIONS,
    URGENT,
    generate,
)
from app.rag.retrieval import search

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--dataset", type=Path, default=ROOT / "data/evaluation/generation/questions.jsonl"
)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument(
    "--frozen-results",
    type=Path,
    help="Reuse old evidence by case ID for paired comparison",
)
a = parser.parse_args()
if a.output.exists():
    raise SystemExit("Output exists; use a new name to preserve previous measurements")
frozen = (
    {r["id"]: r["retrieved"] for r in json.loads(a.frozen_results.read_text())["rows"]}
    if a.frozen_results
    else None
)
settings = get_settings()
embedder = E5Embedder(settings) if frozen is None else None
path = a.dataset
rows = []
out = a.output
out.parent.mkdir(parents=True, exist_ok=True)
for line in path.read_text().splitlines():
    case = json.loads(line)
    start = time.monotonic()
    sources = (
        frozen[case["id"]]
        if frozen is not None
        else search(session_factory(), embedder, case["question"], 5)
    )
    audit = []
    try:
        result = generate(settings, case["question"], sources, audit=audit)
        kind = (
            "urgent"
            if result["answer"] == URGENT
            else "abstain"
            if result["answer"] == FALLBACK
            else "supported"
        )
        passed = kind == case["expected"] or (
            case["expected"] == "supported_or_abstain"
            and kind in ["supported", "abstain"]
        )
        row = dict(
            **case,
            result=result,
            kind=kind,
            behavior_pass=passed,
            seconds=round(time.monotonic() - start, 2),
            retrieved=sources,
        )
    except (httpx.HTTPError, ValueError) as exc:
        row = dict(**case, error=type(exc).__name__, behavior_pass=None)
        if isinstance(exc, httpx.HTTPStatusError):
            row["http_status"] = exc.response.status_code
            try:
                row["error_code"] = exc.response.json().get("error", {}).get("code")
            except ValueError:
                pass
    row["audit"] = audit
    row["retrieved"] = sources
    rows.append(row)
    out.write_text(
        json.dumps(
            {
                "model": settings.openai_model,
                "review_model": settings.openai_review_model,
                "prompt_version": PROMPT_VERSION,
                "prompt_sha256": hashlib.sha256(
                    (INSTRUCTIONS + REVIEW_INSTRUCTIONS).encode()
                ).hexdigest(),
                "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "evidence_mode": "frozen" if frozen is not None else "live",
                "metadata_weight": settings.retrieval_metadata_weight,
                "embedding_revision": settings.embedding_revision,
                "scope": "technical behavior; manual semantic review required; not clinical evaluation",
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(
        case["id"], row.get("kind", row.get("error")), row["behavior_pass"], flush=True
    )
