import pytest
from pypdf import PdfWriter

from app.rag.documents import Section, chunk_sections, read_sections
from tests.conftest import WordTokenizer


def test_markdown_headings_and_line_locations(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("# Гарчиг\n\nМонгол текст.\n\n## Next\nOther text.")
    sections = read_sections(path)
    assert [s.locator for s in sections] == ["Гарчиг; line 3", "Next; line 6"]
    assert sections[0].text == "Монгол текст."


def test_chunk_bounds_overlap_and_coverage():
    text = " ".join(f"үг{i}" for i in range(73))
    chunks = chunk_sections([Section(text, "page 2")], WordTokenizer(), 16, 4)
    assert all(c.token_count <= 16 for c in chunks)
    assert chunks[0].text.split()[-4:] == chunks[1].text.split()[:4]
    assert set(text.split()) == {word for c in chunks for word in c.text.split()}
    assert all(c.locator.startswith("page 2; part ") for c in chunks)


@pytest.mark.parametrize("limit,overlap", [(10, 10), (10, -1), (0, 0)])
def test_bad_chunk_configuration(limit, overlap):
    with pytest.raises(ValueError):
        chunk_sections([Section("hello", "page 1")], WordTokenizer(), limit, overlap)


def test_sentence_boundary():
    chunks = chunk_sections(
        [Section("one two three four. five six seven eight nine ten", "x")], WordTokenizer(), 7, 1
    )
    assert chunks[0].text.endswith("four.")


def test_empty_or_unsupported_documents(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text(" ")
    with pytest.raises(ValueError, match="No extractable text"):
        read_sections(path)
    wrong = tmp_path / "input.exe"
    wrong.write_text("hello")
    with pytest.raises(ValueError, match="Supported file"):
        read_sections(wrong)


def test_scanned_pdf_rejected(tmp_path):
    path = tmp_path / "scan.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(path)
    with pytest.raises(ValueError, match="OCR"):
        read_sections(path)
