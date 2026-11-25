"""Local files only: URLs are citation metadata, never automatic fetch targets."""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class Section:
    text: str
    locator: str


def read_sections(path: Path) -> list[Section]:
    if path.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Document exceeds the 20 MiB prototype limit")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        sections = [
            Section(page.extract_text() or "", f"page {i}")
            for i, page in enumerate(reader.pages, 1)
        ]
        # OCR is deliberately not implicit; empty pages must be inspected by the reviewer.
    elif suffix in {".md", ".txt"}:
        sections = []
        heading = "document"
        paragraph: list[str] = []
        start = 1

        def flush():
            if paragraph:
                sections.append(Section("\n".join(paragraph), f"{heading}; line {start}"))
                paragraph.clear()

        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if suffix == ".md" and line.startswith("#"):
                flush()
                heading = line.lstrip("#").strip() or "document"
            elif not line.strip():
                flush()
            else:
                if not paragraph:
                    start = number
                paragraph.append(line)
        flush()
    else:
        raise ValueError("Supported file types: .md, .txt, text-based .pdf")
    sections = [s for s in sections if s.text.strip()]
    if not sections:
        raise ValueError("No extractable text; scanned PDFs need OCR before ingestion")
    return sections


@dataclass(frozen=True)
class TextChunk:
    text: str
    locator: str
    token_count: int


def chunk_sections(sections: list[Section], tokenizer, limit: int, overlap: int) -> list[TextChunk]:
    if not 0 <= overlap < limit:
        raise ValueError("Require 0 <= overlap < token limit")
    chunks = []
    for section in sections:
        encoded = tokenizer(
            section.text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
            verbose=False,
        )
        offsets = encoded["offset_mapping"]
        start = 0
        part = 1
        while start < len(offsets):
            end = min(start + limit, len(offsets))
            # Prefer a sentence boundary in the latter half of the window.
            if end < len(offsets):
                for candidate in range(end, start + max(limit // 2, overlap + 1), -1):
                    if (
                        section.text[: offsets[candidate - 1][1]]
                        .rstrip()
                        .endswith((".", "?", "!", "。"))
                    ):
                        end = candidate
                        break
            text = section.text[offsets[start][0] : offsets[end - 1][1]].strip()
            count = len(tokenizer(text, add_special_tokens=False)["input_ids"])
            # Retokenization can differ at a substring boundary: shorten until it fits.
            while count > limit and end > start + 1:
                end -= 1
                text = section.text[offsets[start][0] : offsets[end - 1][1]].strip()
                count = len(tokenizer(text, add_special_tokens=False)["input_ids"])
            if text:
                chunks.append(TextChunk(text, f"{section.locator}; part {part}", count))
            if len(chunks) > 5000:
                raise ValueError("Document exceeds the 5000 chunk prototype limit")
            if end == len(offsets):
                break
            start = max(start + 1, end - overlap)
            # Some tokenizers give multiple tokens the same Unicode character offset.
            while start > 0 and offsets[start][0] == offsets[start - 1][0]:
                start += 1
                if start >= end:
                    start = end
                    break
            part += 1
    if not chunks:
        raise ValueError("No chunks produced")
    return chunks
