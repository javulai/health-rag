"""Regression tests for the real WHO PDF preparation workflow."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "who_corpus.py"
spec = importlib.util.spec_from_file_location("who_corpus", SCRIPT)
who = importlib.util.module_from_spec(spec)
spec.loader.exec_module(who)


def test_recommendation_number_is_preserved_when_page_label_removed():
    source = {"id": "example"}
    result = who.clean_page(
        "xi\nExecutive summary\nRecommendation\n3\nStart at six months.\nxi", source
    )
    assert result == "Recommendation 3 Start at six months."


def test_select_preserves_qualifications_and_rejects_missing_marker():
    pages = [
        {
            "text": "heading\nRecommendation 3\nAdvice (conditional). "
            "Remarks: exception.\nRecommendation 4\nOther."
        }
    ]
    selection = {"pages": [1], "start": "Recommendation 3", "end": "Recommendation 4"}
    result = who.select_text(pages, selection, {"id": "example"})
    assert "(conditional)" in result and "Remarks: exception." in result
    with pytest.raises(ValueError, match="not unique"):
        who.select_text(pages, {**selection, "start": "Absent"}, {"id": "example"})


@pytest.mark.parametrize(
    "url",
    [
        "http://iris.who.int/file",
        "https://iris.who.int.evil.example/file",
        "https://localhost/file",
        "https://user:secret@iris.who.int/file",
        "https://iris.who.int:8080/file",
    ],
)
def test_downloader_rejects_unapproved_targets(url):
    with pytest.raises(ValueError):
        who.validate_url(url)


def test_downloader_accepts_official_https():
    who.validate_url("https://iris.who.int/server/api/core/bitstreams/example/content")
