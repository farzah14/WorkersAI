from __future__ import annotations

from datetime import date
from typing import Any

import httpx
from psycopg import AsyncConnection

from jobmatch_worker.config import Settings
from jobmatch_worker.exports.excel import build_excel_bytes
from jobmatch_worker.exports.models import (
    CandidateSummary,
    ExportFilters,
    ExportRequest,
    ExportRow,
    SearchCriteria,
)
from jobmatch_worker.exports.pdf import build_pdf_bytes
from jobmatch_worker.queue import complete_item, fail_item, retry_item

_SCOPE_BEST_MIN_SCORE = 80


def storage_path_for(user_id: str, export_id: str, fmt: str) -> str:
    extension = "xlsx" if fmt == "xlsx" else "pdf"
    return f"{user_id}/{export_id}/report.{extension}"


def candidate_summary_from_profile(profile: dict[str, Any]) -> CandidateSummary:
    return CandidateSummary(
        name=profile.get("name") or "",
        headline=profile.get("current_role") or "",
        skills=list(profile.get("skills") or []),
        years_experience=profile.get("experience_years"),
        location="",
        languages=list(profile.get("languages") or []),
        education=list(profile.get("education") or []),
    )


def criteria_from_request(request: ExportRequest) -> SearchCriteria:
    filters = request.filters
    return SearchCriteria(
        scope=request.scope,
        region=filters.region if filters else None,
        work_mode=filters.work_mode if filters else None,
        min_score=filters.min_score if filters else None,
        status=filters.status if filters else None,
        date_from=filters.date_from if filters else None,
        date_to=filters.date_to if filters else None,
    )


def _row_matches(row: ExportRow, filters: ExportFilters) -> bool:
    if filters.region and row.region not in filters.region:
        return False
    if filters.work_mode and row.work_mode not in filters.work_mode:
        return False
    if filters.min_score is not None and row.overall_score < filters.min_score:
        return False
    if filters.status and row.status not in filters.status:
        return False
    if filters.date_from is not None:
        published = row.published_at or date.min
        if published < filters.date_from:
            return False
    if filters.date_to is not None:
        published = row.published_at or date.max
        if published > filters.date_to:
            return False
    return True


def apply_scope_and_filters(
    rows: list[ExportRow],
    scope: str,
    filters: ExportFilters | None,
) -> list[ExportRow]:
    if scope == "best_and_strong":
        return [row for row in rows if row.overall_score >= _SCOPE_BEST_MIN_SCORE]
    if scope == "current_filters" and filters is not None:
        return [row for row in rows if _row_matches(row, filters)]
    return rows


def generate_report(
    fmt: str,
    rows: list[ExportRow],
    candidate: CandidateSummary,
    criteria: SearchCriteria,
) -> bytes:
    if fmt == "xlsx":
        return build_excel_bytes(rows, candidate, criteria)
    return build_pdf_bytes(rows, candidate, criteria)


async def _load_export(
    conn: AsyncConnection[Any], export_id: str
) -> dict[str, Any] | None:
    row = await conn.execute(
        """
        select user_id, search_run_id, format, scope, filter_json
        from public.exports
        where id = %s
        """,
        (export_id,),
    )
    found = await row.fetchone()
    return dict(found) if found else None


async def _load_run(
    conn: AsyncConnection[Any], run_id: str, user_id: str
) -> dict[str, Any] | None:
    row = await conn.execute(
        """
        select candidate_profile_id
        from public.job_search_runs
        where id = %s and user_id = %s
        """,
        (run_id, user_id),
    )
    found = await row.fetchone()
    return dict(found) if found else None


async def _load_profile(
    conn: AsyncConnection[Any], candidate_profile_id: str
) -> dict[str, Any]:
    row = await conn.execute(
        "select profile from public.candidate_profiles where id = %s",
        (candidate_profile_id,),
    )
    found = await row.fetchone()
    if found is None:
        return {}
    return dict(found)["profile"]


async def load_rows(
    conn: AsyncConnection[Any], user_id: str, search_run_id: str
) -> list[ExportRow]:
    row = await conn.execute(
        """
        select
          j.title as job_title,
          j.company,
          j.location,
          j.region,
          j.work_mode,
          j.employment_type,
          j.salary_min,
          j.salary_max,
          j.salary_currency as currency,
          j.published_at::date as published_at,
          m.overall_score::float,
          m.skills_score::float,
          m.experience_score::float,
          m.education_score::float,
          m.location_score::float,
          m.seniority_score::float,
          m.language_score::float,
          m.verdict,
          m.strengths,
          m.gaps,
          m.critical_gaps,
          m.recommendations,
          j.source_name,
          j.original_url,
          coalesce(uj.status, 'new') as status
        from public.job_matches as m
        join public.jobs as j on j.id = m.job_id
        left join public.user_jobs as uj
          on uj.job_id = m.job_id and uj.user_id = m.user_id
        where m.user_id = %s and m.search_run_id = %s
        order by m.overall_score desc, j.published_at desc nulls last, j.title
        """,
        (user_id, search_run_id),
    )
    found = await row.fetchall()
    return [ExportRow.model_validate(dict(r)) for r in found]


async def _mark_status(
    conn: AsyncConnection[Any],
    export_id: str,
    status: str,
    storage_path: str | None = None,
    error_code: str | None = None,
) -> None:
    await conn.execute(
        """
        update public.exports
        set status = %s, storage_path = %s, error_code = %s,
            completed_at = case when %s = 'completed' then now() else completed_at end
        where id = %s
        """,
        (status, storage_path, error_code, status, export_id),
    )


async def _upload_report(
    settings: Settings,
    path: str,
    blob: bytes,
) -> None:
    async with httpx.AsyncClient(
        base_url=f"{settings.supabase_url}/storage/v1",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        },
        timeout=120.0,
    ) as client:
        response = await client.post(
            f"/object/{settings.exports_bucket}/{path}",
            content=blob,
            headers={"Content-Type": "application/octet-stream"},
        )
        response.raise_for_status()


async def handle_generate_export(
    conn: AsyncConnection[Any],
    item: dict[str, Any],
    settings: Settings,
) -> None:
    payload = item.get("payload") or {}
    export_id = payload.get("export_id")
    if not export_id:
        await fail_item(conn, str(item["id"]), "payload missing export_id")
        return

    export = await _load_export(conn, str(export_id))
    if export is None:
        await fail_item(conn, str(item["id"]), "export not found")
        return
    if export["status"] == "completed":
        await complete_item(conn, str(item["id"]))
        return

    try:
        run = await _load_run(conn, export["search_run_id"], export["user_id"])
        if run is None:
            await _mark_status(conn, str(export_id), "failed", error_code="export_run_missing")
            await complete_item(conn, str(item["id"]))
            return

        request = ExportRequest(
            export_id=str(export_id),
            user_id=export["user_id"],
            search_run_id=export["search_run_id"],
            format=export["format"],
            scope=export["scope"],
            filters=(
                ExportFilters.model_validate(export["filter_json"])
                if export.get("filter_json")
                else None
            ),
        )

        await _mark_status(conn, str(export_id), "processing")

        profile = await _load_profile(conn, run["candidate_profile_id"])
        candidate = candidate_summary_from_profile(profile)
        criteria = criteria_from_request(request)
        rows = await load_rows(conn, export["user_id"], export["search_run_id"])
        selected = apply_scope_and_filters(rows, request.scope, request.filters)

        blob = generate_report(request.format, selected, candidate, criteria)
        path = storage_path_for(export["user_id"], str(export_id), request.format)
        await _upload_report(settings, path, blob)

        await _mark_status(conn, str(export_id), "completed", storage_path=path)
        await complete_item(conn, str(item["id"]))
    except Exception as exc:  # noqa: BLE001 - heterogeneous transient failures
        await conn.rollback()
        attempt = int(item.get("attempts") or 0)
        if attempt >= settings.max_attempts:
            await _mark_status(conn, str(export_id), "failed", error_code="export_generation_failed")
            await fail_item(conn, str(item["id"]), str(exc))
        else:
            await retry_item(conn, str(item["id"]), str(exc), attempt)