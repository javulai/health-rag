"""Reproduce the pinned WHO starter corpus; run with backend/.venv/bin/python."""

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
CATALOG = ROOT / "data/sources/who/catalog.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in {
        "www.who.int",
        "iris.who.int",
    }:
        raise ValueError("Only the explicitly reviewed WHO HTTPS hosts are permitted")
    if parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise ValueError("Invalid WHO source URL")


class WhoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(catalog, raw):
    raw.mkdir(parents=True, exist_ok=True)
    for source in catalog["sources"]:
        path = raw / f"{source['id']}.pdf"
        if not path.exists():
            validate_url(source["pdf_url"])
            request = Request(source["pdf_url"], headers={"User-Agent": "ThesisResearch/0.1"})
            with build_opener(WhoRedirect).open(request, timeout=40) as response:
                payload = response.read(20 * 1024 * 1024 + 1)
            if len(payload) > 20 * 1024 * 1024 or not payload.startswith(b"%PDF-"):
                raise ValueError("Expected a PDF no larger than 20 MiB")
            if hashlib.sha256(payload).hexdigest() != source["sha256"]:
                raise ValueError("Remote PDF changed. Review it as a new corpus batch")
            path.write_bytes(payload)
        if digest(path) != source["sha256"]:
            raise ValueError(f"Snapshot checksum mismatch: {source['id']}")
        print(f"Verified {source['id']}")


def clean_page(text, source):
    # Only exact running headers/footers and whitespace are removed, not medical qualifiers.
    headers = {
        "GUIDELINE: COUNSELLING OF WOMEN TO IMPROVE BREASTFEEDING PRACTICES",
        "Guideline: protecting, promoting and supporting breastfeeding in facilities "
        "providing maternity and newborn services",
        "WHO Guideline for complementary feeding of infants and young children 6–23 months of age",
        "Infant and young child feeding counselling: an integrated course. "
        "Guidance on the use of counselling cards",
        "Counselling cards: key practices and discussion points",
        "Executive summary",
    }
    lines = []
    original_lines = text.splitlines()
    for number, line in enumerate(original_lines):
        line = line.strip()
        if not line or line in headers:
            continue
        if (number < 2 or number >= len(original_lines) - 2) and re.fullmatch(
            r"(?:\d+|[ivxlcdmIVXLCDM]+)", line
        ):
            continue
        # Some running headers combine their page label and title on one line.
        if any(re.fullmatch(r"[ivxlcdm]+\s+" + re.escape(h), line) for h in headers):
            continue
        if re.fullmatch(r"Executive summary\s+[ivxlcdm]+", line):
            continue
        lines.append(line)
    # Do not automatically dehyphenate: retain source spellings and avoid changing compound terms.
    return re.sub(r"\s+", " ", " ".join(lines)).replace("\u00ad", "").strip()


def select_text(pages, selection, source):
    text = " ".join(clean_page(pages[number - 1]["text"], source) for number in selection["pages"])
    for key in ("start", "end"):
        marker = selection.get(key)
        if marker:
            if text.count(marker) != 1:
                raise ValueError(f"Selection marker is not unique: {source['id']}: {marker}")
            position = text.index(marker)
            text = text[position:] if key == "start" else text[:position]
    if len(text) < 40 or "\ufffd" in text:
        raise ValueError("Empty or damaged extraction")
    return text.strip()


def prepare(catalog, raw, processed):
    from pypdf import PdfReader

    records = []
    for source in catalog["sources"]:
        path = raw / f"{source['id']}.pdf"
        if digest(path) != source["sha256"]:
            raise ValueError("Source checksum mismatch; re-review before extraction")
        reader = PdfReader(path)
        selected = {n for section in source["sections"] for n in section["pages"]}
        pages = [
            {
                "page": n,
                "label": reader.page_labels[n - 1],
                "text": page.extract_text() or "",
            }
            for n, page in enumerate(reader.pages, 1)
        ]
        license_text = pages[source["license_page"] - 1]["text"]
        normalized_license = re.sub(r"\s+", " ", license_text)
        if "CC BY-NC-SA 3.0 IGO" not in normalized_license:
            raise ValueError(f"Expected open licence not found: {source['id']}")
        save_json(processed / f"{source['id']}.pages.json", pages)
        (processed / f"{source['id']}.license.txt").write_text(license_text, encoding="utf-8")
        record = {
            "id": source["id"],
            "pdf_sha256": source["sha256"],
            "pdf_pages": len(pages),
            "selected_pdf_pages": sorted(selected),
            "snapshot_saved_at": datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
            "indexed": source["index"],
            "role": source["role"],
        }
        if source["index"]:
            content = [f"# {source['title']}", ""]
            for section in source["sections"]:
                pdf_pages = ",".join(str(n) for n in section["pages"])
                printed = ",".join(pages[n - 1]["label"] for n in section["pages"])
                content.extend(
                    [
                        f"## {section['name']} | PDF pages {pdf_pages}; printed {printed}",
                        "",
                        select_text(pages, section, source),
                        "",
                    ]
                )
            extracted = processed / f"{source['id']}.md"
            extracted.write_text("\n".join(content), encoding="utf-8")
            record["extracted_sha256"] = digest(extracted)
            save_json(
                processed / f"{source['id']}.metadata.json",
                {
                    "url": source["url"],
                    "title": source["title"],
                    "organization": source["organization"],
                    "language": "en",
                    "topic": source["topic"],
                    "published_at": source["published_at"],
                    "updated_at": None,
                    "reuse_note": f"{source['license']}; {source['license_url']} "
                    f"Non-commercial thesis research. PDF licence page {source['license_page']}. "
                    "Selected text with formatting/section headings adapted for retrieval; "
                    "no WHO endorsement. "
                    "Original PDF and attribution retained in WHO source catalog. "
                    "Text adaptation licence: CC BY-NC-SA 4.0. " + source["scope_note"],
                },
            )
        records.append(record)
    save_json(processed / "manifest.json", {"batch": catalog["batch"], "records": records})
    print(
        f"Prepared {sum(s['index'] for s in catalog['sources'])} retrieval documents; "
        f"{sum(not s['index'] for s in catalog['sources'])} research reference"
    )


def load(catalog, processed, activate_versions, reviewer):
    from app.core.config import Settings
    from app.modules.knowledge.service import (
        SourceMetadata,
        activate,
        ingest,
        inspect_version,
    )
    from app.rag.embeddings import E5Embedder
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    if activate_versions and not reviewer:
        raise ValueError("Activation requires an explicit technical reviewer label")
    settings = Settings(
        _env_file=ROOT / ".env",
        raw_data_dir=ROOT / "data/raw/who/archive",
        hf_home=ROOT / "data/models",
    )
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    embedder = E5Embedder(settings)
    manifest = json.loads((processed / "manifest.json").read_text())
    expected = {r["id"]: r for r in manifest["records"]}
    records = []
    try:
        for source in catalog["sources"]:
            if not source["index"]:
                continue
            path = processed / f"{source['id']}.md"
            if digest(path) != expected[source["id"]]["extracted_sha256"]:
                raise ValueError("Prepared document changed after extraction")
            metadata = SourceMetadata.model_validate_json(
                (processed / f"{source['id']}.metadata.json").read_text()
            )
            result = ingest(factory, settings, embedder, path, metadata)
            from uuid import UUID

            version_id = UUID(result["version_id"])
            if activate_versions:
                result.update(activate(factory, version_id, reviewer))
            inspected = inspect_version(factory, version_id)
            save_json(processed / f"{source['id']}.chunks.json", inspected)
            records.append(
                {
                    "id": source["id"],
                    **result,
                    "chunk_count": len(inspected["chunks"]),
                    "review_type": "technical extraction review, not clinical validation",
                }
            )
            print(json.dumps(records[-1], ensure_ascii=False), flush=True)
        save_json(
            processed / "ingestion.json",
            {"model": embedder.identity, "records": records},
        )
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch", "prepare", "ingest"])
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--reviewer")
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    raw = ROOT / "data/raw/who" / catalog["batch"]
    processed = ROOT / "data/processed/who" / catalog["batch"]
    processed.mkdir(parents=True, exist_ok=True)
    if args.action == "fetch":
        fetch(catalog, raw)
    elif args.action == "prepare":
        prepare(catalog, raw, processed)
    else:
        load(catalog, processed, args.activate, args.reviewer)


if __name__ == "__main__":
    main()
