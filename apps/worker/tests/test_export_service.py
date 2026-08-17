from datetime import date

import pytest
from pydantic import ValidationError
from test_excel_export import make_row

from jobmatch_worker.exports.models import (
    CandidateSummary,
    ExportFilters,
    ExportRequest,
    SearchCriteria,
)
from jobmatch_worker.exports.service import (
    apply_scope_and_filters,
    candidate_summary_from_profile,
    criteria_from_request,
    generate_report,
    storage_path_for,
)


def test_export_filters_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ExportFilters.model_validate(
            {"region": ["indonesia"], "drop table": "jobs"}
        )


def test_export_request_validates_scope_and_format() -> None:
    with pytest.raises(ValidationError):
        ExportRequest(
            export_id="e1",
            user_id="u1",
            search_run_id="r1",
            format="csv",
            scope="all",
        )
    with pytest.raises(ValidationError):
        ExportRequest(
            export_id="e1",
            user_id="u1",
            search_run_id="r1",
            format="xlsx",
            scope="everything",
        )


def test_scope_all_keeps_every_row() -> None:
    rows = [make_row(job_title="A", overall_score=95), make_row(job_title="B", overall_score=55)]
    assert apply_scope_and_filters(rows, "all", None) == rows


def test_scope_best_and_strong_keeps_only_80_plus() -> None:
    rows = [
        make_row(job_title="A", overall_score=95),
        make_row(job_title="B", overall_score=81),
        make_row(job_title="C", overall_score=79),
    ]
    result = apply_scope_and_filters(rows, "best_and_strong", None)
    assert [r.job_title for r in result] == ["A", "B"]


def test_current_filters_applies_and_semantics() -> None:
    rows = [
        make_row(job_title="A", region="indonesia", work_mode="hybrid", overall_score=90),
        make_row(job_title="B", region="global", work_mode="remote", overall_score=90),
        make_row(job_title="C", region="indonesia", work_mode="hybrid", overall_score=60),
    ]
    filters = ExportFilters(
        region=["indonesia"],
        work_mode=["hybrid"],
        min_score=70,
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
    )
    result = apply_scope_and_filters(rows, "current_filters", filters)
    assert [r.job_title for r in result] == ["A"]


def test_current_filters_filters_by_status() -> None:
    rows = [
        make_row(job_title="A", overall_score=90, status="saved"),
        make_row(job_title="B", overall_score=90, status="applied"),
    ]
    filters = ExportFilters(status=["saved"])
    result = apply_scope_and_filters(rows, "current_filters", filters)
    assert [r.job_title for r in result] == ["A"]


def test_storage_path_uses_user_and_export_ids() -> None:
    assert (
        storage_path_for("user-1", "export-9", "xlsx")
        == "user-1/export-9/report.xlsx"
    )
    assert (
        storage_path_for("user-1", "export-9", "pdf")
        == "user-1/export-9/report.pdf"
    )


def test_candidate_summary_maps_profile_json() -> None:
    profile = {
        "name": "Aulia Rahman",
        "current_role": "Backend Engineer",
        "seniority": "mid",
        "target_roles": ["Backend Engineer"],
        "skills": ["Python", "PostgreSQL"],
        "experience_years": 5.0,
        "languages": ["Indonesian", "English"],
        "education": ["S1 Computer Science"],
    }
    summary = candidate_summary_from_profile(profile)
    assert summary.name == "Aulia Rahman"
    assert summary.headline == "Backend Engineer"
    assert summary.skills == ["Python", "PostgreSQL"]
    assert summary.years_experience == 5.0
    assert summary.languages == ["Indonesian", "English"]
    assert summary.education == ["S1 Computer Science"]


def test_criteria_from_request_maps_filters() -> None:
    request = ExportRequest(
        export_id="e1",
        user_id="u1",
        search_run_id="r1",
        format="xlsx",
        scope="current_filters",
        filters=ExportFilters(
            region=["indonesia"],
            min_score=80,
            date_from=date(2026, 8, 1),
        ),
    )
    criteria = criteria_from_request(request)
    assert criteria.scope == "current_filters"
    assert criteria.region == ["indonesia"]
    assert criteria.min_score == 80
    assert criteria.date_from == date(2026, 8, 1)
    assert criteria.date_to is None


def test_generate_report_dispatches_xlsx_and_pdf() -> None:
    rows = [make_row()]
    candidate = CandidateSummary(name="Aulia Rahman")
    criteria = SearchCriteria(scope="all")
    xlsx = generate_report("xlsx", rows, candidate, criteria)
    assert xlsx.startswith(b"PK")
    pdf = generate_report("pdf", rows, candidate, criteria)
    assert pdf.startswith(b"%PDF-")