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



def test_extracts_text_from_table_only_docx(tmp_path: Path) -> None:
    from docx import Document

    doc_path = tmp_path / "table.docx"
    doc = Document()
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].paragraphs[0].text = "Senior Software Engineer with 10 years experience"
    table.rows[0].cells[1].paragraphs[0].text = "Core skills: Python, PostgreSQL, Docker, Kubernetes"
    table.rows[1].cells[0].paragraphs[0].text = "Education: Bachelor of Science in Computer Science"
    table.rows[1].cells[1].paragraphs[0].text = "Languages: English fluent, Bahasa Indonesia native"
    doc.save(str(doc_path))

    text = extract_cv_text(doc_path)
    assert "Senior Software Engineer" in text
    assert "Python, PostgreSQL" in text
    assert len(text) >= 80
def test_rejects_image_only_pdf() -> None:
    with pytest.raises(UnsupportedScannedPdf):
        extract_cv_text(FIXTURES / "image-only.pdf")


def test_rejects_unknown_extension() -> None:
    with pytest.raises(ValueError):
        extract_cv_text(FIXTURES / "sample.txt")