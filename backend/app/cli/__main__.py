import argparse
import json
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import session_factory
from app.modules.knowledge.service import SourceMetadata, activate, ingest, inspect_version
from app.rag.embeddings import E5Embedder
from app.rag.retrieval import search


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def parser():
    root = argparse.ArgumentParser(description="Local knowledge ingestion and retrieval CLI")
    sub = root.add_subparsers(dest="command", required=True)
    ing = sub.add_parser("ingest", help="Create staging chunks from a local file")
    ing.add_argument("file", type=Path)
    ing.add_argument("--metadata", type=Path, required=True, help="SourceMetadata JSON")
    inspect = sub.add_parser("inspect", help="Review all chunks before activation")
    inspect.add_argument("version_id", type=UUID)
    act = sub.add_parser("activate", help="Record review and atomically activate a staging version")
    act.add_argument("version_id", type=UUID)
    act.add_argument("--reviewer", required=True)
    query = sub.add_parser("search", help="Return chunks and source metadata; no generated answer")
    query.add_argument("question")
    query.add_argument("--limit", type=int, default=5)
    evaluation = sub.add_parser("evaluate", help="Evaluate source+locator retrieval recall")
    evaluation.add_argument("dataset", type=Path)
    evaluation.add_argument("--output", type=Path, required=True)
    evaluation.add_argument("--limit", type=int, default=5)
    return root


def main():
    args = parser().parse_args()
    settings = get_settings()
    factory = session_factory()
    try:
        if args.command == "inspect":
            emit(inspect_version(factory, args.version_id))
        elif args.command == "activate":
            emit(activate(factory, args.version_id, args.reviewer))
        else:
            # Validate the input before downloading/loading an embedding model.
            if args.command == "ingest":
                metadata = SourceMetadata.model_validate_json(args.metadata.read_text())
                if not args.file.is_file():
                    raise ValueError("Input file does not exist")
            embedder = E5Embedder(settings)
            if args.command == "ingest":
                emit(ingest(factory, settings, embedder, args.file, metadata))
            elif args.command == "search":
                emit(
                    {
                        "model": embedder.identity,
                        "results": search(factory, embedder, args.question, args.limit),
                    }
                )
            else:
                from app.rag.evaluation import evaluate

                result = evaluate(factory, embedder, args.dataset, args.limit)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
                emit(result["summary"])
    except (ValueError, OSError, SQLAlchemyError) as exc:
        # Do not print connection strings, provider responses, or document content in error logs.
        if isinstance(exc, SQLAlchemyError):
            message = "Database operation failed. Check DATABASE_URL and run alembic upgrade head."
        elif isinstance(exc, OSError):
            message = "File/model access failed. Check paths, model cache and network access."
        else:
            message = str(exc)
        print(f"Error: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
