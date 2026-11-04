from datetime import date
from typing import Any
from uuid import UUID

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
    _load_export,
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


def test_web_shaped_export_filters_validate() -> None:
    filters = ExportFilters.model_validate({
        "region": ["indonesia"],
        "work_mode": ["remote"],
        "min_score": 80,
        "status": ["saved"],
    })
    assert filters.region == ["indonesia"]


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


class ExportQueryCursor:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    async def fetchone(self) -> dict[str, Any]:
        return self.row


class ExportQueryConnection:
    def __init__(self) -> None:
        self.query: str | None = None

    async def execute(self, query: str, params: tuple[str]) -> ExportQueryCursor:
        self.query = query
        if "status" not in query.lower():
            raise AssertionError("export query omitted the status column")
        return ExportQueryCursor(
            {
                "user_id": UUID("00000000-0000-0000-0000-000000000001"),
                "search_run_id": UUID("00000000-0000-0000-0000-000000000002"),
                "format": "xlsx",
                "scope": "all",
                "filter_json": {},
                "status": "queued",
            }
        )


async def test_load_export_reads_status_for_worker_idempotency() -> None:
    conn = ExportQueryConnection()

    export = await _load_export(conn, "export-1")  # type: ignore[arg-type]

    assert export is not None
    assert export["status"] == "queued"
    assert export["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert export["search_run_id"] == "00000000-0000-0000-0000-000000000002"


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


def test_export_filters_accept_expanded_dashboard_fields() -> None:
    filters = ExportFilters.model_validate(
        {
            "query": "  SENIOR   Engineer ",
            "employment_type": ["full-time"],
            "source_name": ["Greenhouse"],
            "work_mode": ["remote"],
            "min_score": 70,
            "exclude_ignored": True,
        }
    )
    assert filters.query == "senior engineer"
    assert filters.employment_type == ["full-time"]
    assert filters.source_name == ["Greenhouse"]
    assert filters.exclude_ignored is True


@pytest.mark.parametrize(
    "payload",
    [
        {"employment_type": ["permanent"]},
        {"source_name": ["   "]},
        {"source_name": ["s" * 201]},
        {"query": "a" * 201},
        {"exclude_ignored": "true"},
        {"employment_type": ["full-time"] * 9},
        {"source_name": ["greenhouse"] * 21},
        {"date_from": date(2026, 9, 30), "date_to": date(2026, 9, 1)},
    ],
)
def test_export_filters_reject_invalid_expanded_fields(payload: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ExportFilters.model_validate(payload)


def test_current_filters_matches_query_in_title_or_company_only() -> None:
    rows = [
        make_row(job_title="Engineer", company="ACME Labs"),
        make_row(job_title="Data Analyst", company="Beta"),
        make_row(job_title="Designer", company="ACME", location="ACME Street"),
    ]
    filters = ExportFilters(query="acme")
    result = apply_scope_and_filters(rows, "current_filters", filters)
    assert [r.company for r in result] == ["ACME Labs", "ACME"]


def test_current_filters_matches_employment_type_and_source_exactly() -> None:
    rows = [
        make_row(job_title="A", employment_type="full-time", source_name="Greenhouse"),
        make_row(job_title="B", employment_type="contract", source_name="Greenhouse"),
        make_row(job_title="C", employment_type="full-time", source_name="greenhouse"),
        make_row(job_title="D", employment_type=None, source_name="Greenhouse"),
    ]
    filters = ExportFilters(employment_type=["full-time"], source_name=["Greenhouse"])
    result = apply_scope_and_filters(rows, "current_filters", filters)
    assert [r.job_title for r in result] == ["A"]


def test_current_filters_exclude_ignored_is_and_combined_with_explicit_status() -> None:
    rows = [
        make_row(job_title="ignored", status="ignored"),
        make_row(job_title="new", status="new"),
        make_row(job_title="saved", status="saved"),
    ]
    assert [
        r.job_title
        for r in apply_scope_and_filters(
            rows, "current_filters", ExportFilters(exclude_ignored=True)
        )
    ] == ["new", "saved"]
    # The boolean and status predicates are AND, never override each other.
    assert [
        r.job_title
        for r in apply_scope_and_filters(
            rows,
            "current_filters",
            ExportFilters(exclude_ignored=True, status=["ignored"]),
        )
    ] == []
    assert [
        r.job_title
        for r in apply_scope_and_filters(
            rows, "current_filters", ExportFilters(status=["ignored"])
        )
    ] == ["ignored"]


def test_scope_all_ignores_expanded_filters_for_legacy_compatibility() -> None:
    rows = [make_row(job_title="ignored", status="ignored")]
    filters = ExportFilters(query="nothing", exclude_ignored=True)
    assert apply_scope_and_filters(rows, "all", filters) == rows


def test_query_strasse_does_not_match_sharp_s() -> None:
    rows = [make_row(job_title="Stra\u00dfe Engineer", company="Example")]
    result = apply_scope_and_filters(
        rows, "current_filters", ExportFilters(query="strasse")
    )
    assert result == []


def test_query_nfc_matches_composed_and_decomposed_spellings() -> None:
    rows = [
        make_row(job_title="Caf\u00e9 Engineer", company="One"),
        make_row(job_title="Cafe\u0301 Engineer", company="Two"),
    ]
    result = apply_scope_and_filters(
        rows, "current_filters", ExportFilters(query="cafe\u0301")
    )
    assert [r.company for r in result] == ["One", "Two"]


def test_criteria_from_request_includes_expanded_fields() -> None:
    request = ExportRequest(
        export_id="e1",
        user_id="u1",
        search_run_id="r1",
        format="xlsx",
        scope="current_filters",
        filters=ExportFilters(
            query="engineer",
            employment_type=["full-time"],
            source_name=["greenhouse"],
            exclude_ignored=True,
        ),
    )
    criteria = criteria_from_request(request)
    assert criteria.query == "engineer"
    assert criteria.employment_type == ["full-time"]
    assert criteria.source_name == ["greenhouse"]
    assert criteria.exclude_ignored is True


@pytest.mark.asyncio
async def test_load_rows_filters_active_jobs_only() -> None:
    from jobmatch_worker.exports.service import load_rows

    executed_sql: list[str] = []

    class FakeCursor:
        async def fetchall(self) -> list[dict[str, Any]]:
            return []

    class FakeConnection:
        async def execute(self, sql: str, params: tuple[Any, ...]) -> FakeCursor:
            executed_sql.append(sql)
            return FakeCursor()

    await load_rows(FakeConnection(), "user-1", "run-1")  # type: ignore[arg-type]
    assert len(executed_sql) == 1
    assert "j.status = 'active'" in executed_sql[0]
