
from pypdf import PdfReader
from test_excel_export import make_candidate, make_criteria, make_row

from jobmatch_worker.exports.pdf import build_pdf_bytes


def read_pdf(blob: bytes) -> PdfReader:
    return PdfReader(__import__("io").BytesIO(blob))


def pdf_text(blob: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in read_pdf(blob).pages)


def test_pdf_starts_with_pdf_magic() -> None:
    blob = build_pdf_bytes([make_row()], make_candidate(), make_criteria())
    assert blob.startswith(b"%PDF-")


def test_pdf_contains_candidate_and_criteria_summary() -> None:
    blob = build_pdf_bytes([make_row()], make_candidate(), make_criteria())
    text = pdf_text(blob)
    assert "Aulia Rahman" in text
    assert "Backend Engineer, 5 years" in text
    assert "best_and_strong" in text
    assert "80" in text


def test_pdf_contains_top_match_job_titles() -> None:
    rows = [
        make_row(job_title="Senior Backend Engineer", company="PT Contoh Nusantara"),
        make_row(job_title="Data Engineer", company="Contoh Data Corp"),
    ]
    blob = build_pdf_bytes(rows, make_candidate(), make_criteria())
    text = pdf_text(blob)
    assert "Senior Backend Engineer" in text
    assert "Data Engineer" in text


def test_pdf_contains_link_annotations_for_job_urls() -> None:
    rows = [
        make_row(job_title="Senior Backend Engineer", original_url="https://example.com/jobs/42"),
        make_row(job_title="Data Engineer", original_url="https://example.com/jobs/43"),
    ]
    blob = build_pdf_bytes(rows, make_candidate(), make_criteria())
    uris: set[str] = set()
    for page in read_pdf(blob).pages:
        for annotation in page.annotations or []:
            obj = annotation.get_object()
            action = obj.get("/A")
            if action is not None and action.get_object().get("/URI"):
                uris.add(action.get_object()["/URI"])
    assert "https://example.com/jobs/42" in uris
    assert "https://example.com/jobs/43" in uris


def test_pdf_escapes_user_and_job_text_before_markup() -> None:
    row = make_row(
        job_title="Engineer & Analyst <b>bold</b>",
        company="Contoh & Sons",
        strengths=["Python", "SQL <queries>"],
    )
    blob = build_pdf_bytes([row], make_candidate(), make_criteria())
    text = pdf_text(blob)
    assert "Engineer & Analyst" in text
    assert "Contoh & Sons" in text
    assert "SQL <queries>" in text
    assert "<b>" in text
    assert "&lt;" not in text


def test_pdf_includes_aggregate_stats_and_all_exported_rows() -> None:
    rows = [make_row(job_title="A", overall_score=92.0), make_row(job_title="B", overall_score=81.0)]
    blob = build_pdf_bytes(rows, make_candidate(), make_criteria())
    text = pdf_text(blob)
    assert "2" in text
    assert "92.0" in text
    assert "81.0" in text