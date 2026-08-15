from pathlib import Path

import pytest

from jobmatch_worker.cv.extract import UnsupportedScannedPdf, extract_cv_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_text_from_pdf() -> None:
    text = extract_cv_text(FIXTURES / "sample.pdf")
    assert "Python" in text
    assert "Jane Doe" in text


def test_extracts_text_from_docx() -> None:
    text = extract_cv_text(FIXTURES / "sample.docx")
    assert "Python" in text
    assert "BigQuery" in text


def test_rejects_image_only_pdf() -> None:
    with pytest.raises(UnsupportedScannedPdf):
        extract_cv_text(FIXTURES / "image-only.pdf")


def test_rejects_unknown_extension() -> None:
    with pytest.raises(ValueError):
        extract_cv_text(FIXTURES / "sample.txt")