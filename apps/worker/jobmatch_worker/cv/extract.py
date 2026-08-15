from pathlib import Path

import pymupdf
from docx import Document

MIN_TEXT_LENGTH = 80


class UnsupportedScannedPdf(ValueError):
    """Raised when a PDF contains no text layer (scanned/image-only)."""


def _from_pdf(path: Path) -> str:
    doc = pymupdf.open(path)
    try:
        text = "\n".join(doc[i].get_text() for i in range(doc.page_count))
    finally:
        doc.close()
    if len(text.strip()) < MIN_TEXT_LENGTH:
        raise UnsupportedScannedPdf("PDF has no text layer; scanned CVs are not supported")
    return text


def _from_docx(path: Path) -> str:
    doc = Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs)
    if len(text.strip()) < MIN_TEXT_LENGTH:
        raise ValueError("DOCX contains no readable text")
    return text


def extract_cv_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _from_pdf(path)
    if suffix == ".docx":
        return _from_docx(path)
    raise ValueError(f"Unsupported CV format: {suffix}")