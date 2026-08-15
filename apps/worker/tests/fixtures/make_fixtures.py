"""Generate synthetic CV fixtures for extraction tests.

Synthetic content only - no real PII. Run with: uv run python tests/fixtures/make_fixtures.py
"""

from pathlib import Path

import pymupdf
from docx import Document

HERE = Path(__file__).parent
TEXT = (
    "Jane Doe\nSoftware Engineer\n"
    "Python, SQL, ETL, BigQuery\n"
    "Worked on data pipelines and analytics platforms for 5 years.\n"
)


def make_sample_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), TEXT)
    doc.save(path)
    doc.close()


def make_sample_docx(path: Path) -> None:
    doc = Document()
    for line in TEXT.splitlines():
        doc.add_paragraph(line)
    doc.save(path)


def make_image_only_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(50, 50, 250, 250), color=(0, 0, 0), fill=True)
    doc.save(path)
    doc.close()


def main() -> None:
    make_sample_pdf(HERE / "sample.pdf")
    make_sample_docx(HERE / "sample.docx")
    make_image_only_pdf(HERE / "image-only.pdf")
    print("fixtures written")


if __name__ == "__main__":
    main()
