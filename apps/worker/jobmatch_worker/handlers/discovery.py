"""Orchestrate resilient job discovery runs."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection

from jobmatch_worker.config import Settings
from jobmatch_worker.jobs.canonicalize import canonicalize_url
from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceConnector,
    SourceDataError,
    SourceError,
    SourceUnavailable,
)
from jobmatch_worker.jobs.connectors.career_page import (
    CareerPageContent,
    CareerPageFetcher,
)
from jobmatch_worker.jobs.connectors.tavily import TavilyConnector
from jobmatch_worker.jobs.dedupe import (
    dedupe_jobs,
    is_fuzzy_duplicate,
    job_fingerprint,
    upsert_jobs,
)
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.normalize import NormalizedJob, normalize_job
from jobmatch_worker.jobs.query import SearchQuery, build_queries
from jobmatch_worker.queue import complete_item, enqueue_item, fail_item, retry_item

_SOURCE_CONCURRENCY = 4
_MAX_SOURCE_RESULTS = 200
_MAX_CAREER_CANDIDATES = 120
_MAX_JOBS_PER_RUN = 2
_MAX_TITLE_CHARS = 300
_MAX_COMPANY_CHARS = 300
_MAX_LOCATION_CHARS = 300
_MAX_DESCRIPTION_CHARS = 100_000
_RUN_SELECT_SQL = """
select r.id, r.status, r.trigger, r.candidate_profile_id,
       sp.region, sp.target_roles, sp.locations, sp.work_modes,
       sp.excluded_keywords
from public.job_search_runs r
join public.search_profiles sp on sp.id = r.search_profile_id
where r.id = %s
"""
_SOURCE_TYPES = {
    "tavily": "search",
    "greenhouse": "ats",
    "lever": "ats",
    "career_page": "page",
}
FetchPage = Callable[[str], Awaitable[CareerPageContent]]


@dataclass(frozen=True, slots=True)
class _SourceOutcome:
    source_key: str
    status: str
    jobs: tuple[DiscoveredJob, ...] = ()
    error_code: str | None = None
    discovered_count: int = 0
    retryable: bool = False


def _source_type(source_key: str) -> str:
    return _SOURCE_TYPES.get(source_key, "api")


def _error_code(error: SourceError) -> str:
    if isinstance(error, SourceUnavailable):
        return "unavailable"
    if isinstance(error, SourceConfigError):
        return "config"
    if isinstance(error, SourceDataError):
        return "data"
    return "source_error"


def _build_sources(settings: Settings) -> dict[str, SourceConnector]:
    # MVP discovery uses Tavily only; ATS connectors remain available for a
    # future explicitly configured source rollout.
    return {"tavily": TavilyConnector(api_key=settings.tavily_api_key)}


def _candidate_title(candidate: DiscoveryCandidateUrl, text: str) -> str:
    if candidate.title and candidate.title.strip():
        return candidate.title.strip()
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return "Untitled job"


async def _candidate_to_job(
    candidate: DiscoveryCandidateUrl,
    fetch_page: FetchPage,
    source_key: str,
) -> DiscoveredJob | None:
    content = await fetch_page(candidate.url)
    text = content.text.strip()
    if not text:
        raise SourceDataError("career_page", "empty page text")
    if content.is_closed:
        raise SourceDataError(source_key, "job page is closed")
    if not content.company:
        raise SourceDataError(source_key, "job page missing company metadata")
    job = DiscoveredJob(
        source_name="Tavily",
        source_key=source_key,
        title=content.title or _candidate_title(candidate, text),
        company=content.company,
        location=content.location,
        work_mode=content.work_mode,
        description=text,
        original_url=candidate.url,
        published_at=content.published_at,
    )
    _validate_job_size(job, source_key)
    return job


def _validate_job_size(job: DiscoveredJob, source_key: str) -> None:
    fields = (
        ("title", job.title, _MAX_TITLE_CHARS),
        ("company", job.company, _MAX_COMPANY_CHARS),
        ("location", job.location, _MAX_LOCATION_CHARS),
        ("description", job.description, _MAX_DESCRIPTION_CHARS),
    )
    if any("\x00" in value for _, value, _ in fields if value is not None):
        raise SourceDataError(source_key, "job contains a NUL character")
    for name, value, limit in fields:
        if value is not None and len(value) > limit:
            raise SourceDataError(source_key, f"job {name} exceeds size limit")


def _queries_for_source(source_key: str, queries: list[SearchQuery]) -> list[SearchQuery]:
    if source_key in {"greenhouse", "lever"}:
        # These ATS endpoints return a complete board/site and do not accept
        # the free-form query; fetching it once avoids repeated full scans.
        return queries[:1]
    return queries


async def _run_source(
    source_key: str,
    connector: SourceConnector,
    queries: list[SearchQuery],
    fetch_page: FetchPage | None,
    semaphore: asyncio.Semaphore,
) -> _SourceOutcome:
    jobs: list[DiscoveredJob] = []
    discovered_count = 0
    candidate_failures = 0
    candidate_retryable = False
    seen_candidates: set[str] = set()
    try:
        async with semaphore:
            for query in _queries_for_source(source_key, queries):
                results = await connector.search(query)
                for result in results:
                    discovered_count += 1
                    if discovered_count > _MAX_SOURCE_RESULTS:
                        raise SourceDataError(source_key, "source result limit exceeded")
                    if isinstance(result, DiscoveryCandidateUrl):
                        if fetch_page is None:
                            continue
                        try:
                            candidate_url = canonicalize_url(
                                result.url, source_key=source_key
                            )
                        except SourceError:
                            candidate_failures += 1
                            continue
                        if candidate_url in seen_candidates:
                            continue
                        if len(seen_candidates) >= _MAX_CAREER_CANDIDATES:
                            raise SourceDataError(
                                source_key, "career-page candidate limit exceeded"
                            )
                        seen_candidates.add(candidate_url)
                        try:
                            job = await _candidate_to_job(result, fetch_page, source_key)
                        except SourceUnavailable:
                            candidate_failures += 1
                            candidate_retryable = True
                            continue
                        except SourceError:
                            candidate_failures += 1
                            continue
                        if job is not None:
                            jobs.append(job)
                    else:
                        _validate_job_size(result, source_key)
                        jobs.append(result)
    except SourceError as error:
        return _SourceOutcome(
            source_key=source_key,
            status="failed",
            jobs=tuple(jobs),
            error_code=_error_code(error),
            discovered_count=discovered_count,
            retryable=isinstance(error, SourceUnavailable) or candidate_retryable,
        )
    except Exception:  # noqa: BLE001 - isolate one broken source from the run
        return _SourceOutcome(
            source_key=source_key,
            status="failed",
            jobs=tuple(jobs),
            error_code="source_error",
            discovered_count=discovered_count,
            retryable=True,
        )
    return _SourceOutcome(
        source_key=source_key,
        status="failed" if candidate_failures else "success",
        jobs=tuple(jobs),
        error_code="candidate_fetch" if candidate_failures else None,
        discovered_count=discovered_count,
        retryable=candidate_retryable,
    )


async def _update_run(
    conn: AsyncConnection[Any],
    *,
    run_id: str,
    status: str,
    discovered_count: int,
    normalized_count: int,
    duplicate_count: int,
    failed_count: int,
    terminal: bool = True,
) -> None:
    if terminal:
        query = """
        update public.job_search_runs
        set status = %s,
            discovered_count = %s,
            normalized_count = %s,
            duplicate_count = %s,
            failed_count = %s,
            completed_at = now()
        where id = %s
        """
    else:
        query = """
        update public.job_search_runs
        set status = %s,
            discovered_count = %s,
            normalized_count = %s,
            duplicate_count = %s,
            failed_count = %s,
            completed_at = null
        where id = %s
        """
    await conn.execute(
        query,
        (
            status,
            discovered_count,
            normalized_count,
            duplicate_count,
            failed_count,
            run_id,
        ),
    )


async def _record_source(
    conn: AsyncConnection[Any],
    *,
    run_id: str,
    outcome: _SourceOutcome,
) -> None:
    await conn.execute(
        """
        update public.job_sources
        set status = %s, result_count = %s, error_code = %s
        where search_run_id = %s and source_type = %s and source_key = %s
        """,
        (
            outcome.status,
            len(outcome.jobs),
            outcome.error_code,
            run_id,
            _source_type(outcome.source_key),
            outcome.source_key,
        ),
    )


async def _persist_provenance(
    conn: AsyncConnection[Any],
    *,
    run_id: str,
    all_jobs: list[NormalizedJob],
    kept_jobs: list[NormalizedJob],
    job_ids: tuple[str, ...],
) -> None:
    if len(kept_jobs) != len(job_ids):
        raise RuntimeError("job upsert returned misaligned job ids")
    ids_by_fingerprint = {
        job_fingerprint(job): job_id
        for job, job_id in zip(kept_jobs, job_ids, strict=True)
    }
    for job in all_jobs:
        survivor = next(
            (
                kept
                for kept in kept_jobs
                if job_fingerprint(kept) == job_fingerprint(job)
                or is_fuzzy_duplicate(kept, job)
            ),
            None,
        )
        if survivor is None:
            raise RuntimeError("could not map job provenance to a survivor")
        await conn.execute(
            """
            insert into public.job_provenance
              (job_id, search_run_id, source_type, source_key,
               original_url, canonical_url)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (search_run_id, job_id, source_type, source_key) do nothing
            """,
            (
                ids_by_fingerprint[job_fingerprint(survivor)],
                run_id,
                _source_type(job.source_key),
                job.source_key,
                job.original_url,
                job.canonical_url,
            ),
        )


async def _enqueue_requirement_work(
    conn: AsyncConnection[Any],
    *,
    run_id: str,
    jobs: list[NormalizedJob],
    job_ids: tuple[str, ...],
    extraction_enabled: bool,
) -> bool:
    if len(jobs) != len(job_ids):
        raise RuntimeError("job upsert returned misaligned requirement ids")

    cache_cursor = await conn.execute(
        """
        select job_id, description_hash
        from public.job_requirements
        where job_id = any(%s)
        """,
        (list(job_ids),),
    )
    cached_hashes = {
        str(row["job_id"]): row["description_hash"]
        for row in await cache_cursor.fetchall()
    }

    has_downstream_work = False
    for job, job_id in zip(jobs, job_ids, strict=True):
        description_hash = hashlib.sha256(job.description.encode("utf-8")).hexdigest()
        if cached_hashes.get(str(job_id)) == description_hash:
            await enqueue_item(
                conn,
                kind="match_job",
                dedupe_key=f"match_job:{run_id}:{job_id}:{description_hash}",
                payload={"search_run_id": run_id, "job_id": job_id},
            )
            has_downstream_work = True
            continue
        if not extraction_enabled:
            continue
        # Plan 4 adds the persistent requirement cache; this key is the
        # interim idempotency boundary for discovery retries.
        await enqueue_item(
            conn,
            kind="extract_job_requirements",
            dedupe_key=f"extract_job_requirements:{job_id}:{description_hash}",
            payload={"job_id": job_id, "description_hash": description_hash},
        )
        has_downstream_work = True
    return has_downstream_work


async def _close_sources(sources: dict[str, SourceConnector]) -> None:
    for source in sources.values():
        close = getattr(source, "aclose", None)
        if close is not None:
            try:
                await close()
            except Exception:  # noqa: BLE001, S110 - teardown is best effort
                pass


async def handle_discover_jobs(
    conn: AsyncConnection[Any],
    item: dict[str, Any],
    settings: Settings,
    *,
    connectors: dict[str, SourceConnector] | None = None,
    fetch_page: FetchPage | None = None,
) -> None:
    """Process one ``discover_jobs`` work item without losing good sources."""
    payload = item.get("payload") or {}
    run_id = payload.get("search_run_id")
    item_id = str(item["id"])
    if not run_id:
        await fail_item(conn, item_id, "payload missing search_run_id")
        return

    cursor = await conn.execute(_RUN_SELECT_SQL, (run_id,))
    run = await cursor.fetchone()
    if run is None:
        await fail_item(conn, item_id, "search run not found")
        return

    await conn.execute(
        """
        update public.job_search_runs
        set status = 'processing', started_at = now()
        where id = %s
        """,
        (run_id,),
    )

    sources = connectors if connectors is not None else _build_sources(settings)
    owned_sources = connectors is None
    page_fetcher: CareerPageFetcher | None = None
    if fetch_page is None:
        page_fetcher = CareerPageFetcher()
        fetch_page = page_fetcher.extract_content

    try:
        try:
            queries = build_queries(
                run["region"],
                list(run["target_roles"]),
                list(run["locations"]),
                remote="remote" in list(run["work_modes"] or []),
                excluded_keywords=list(run["excluded_keywords"] or []),
            )
        except ValueError as error:
            await _update_run(
                conn,
                run_id=run_id,
                status="failed",
                discovered_count=0,
                normalized_count=0,
                duplicate_count=0,
                failed_count=0,
            )
            await fail_item(conn, item_id, f"invalid search profile: {error}")
            return

        for source_key in sources:
            await conn.execute(
                """
                insert into public.job_sources
                  (search_run_id, source_type, source_key, status)
                values (%s, %s, %s, 'queued')
                on conflict (search_run_id, source_type, source_key) do nothing
                """,
                (run_id, _source_type(source_key), source_key),
            )

        semaphore = asyncio.Semaphore(_SOURCE_CONCURRENCY)
        outcomes = await asyncio.gather(
            *(
                _run_source(source_key, source, queries, fetch_page, semaphore)
                for source_key, source in sources.items()
            )
        )
        for outcome in outcomes:
            await _record_source(conn, run_id=run_id, outcome=outcome)

        all_jobs = [job for outcome in outcomes for job in outcome.jobs]
        normalized: list[NormalizedJob] = []
        for job in all_jobs:
            try:
                normalized.append(normalize_job(job, region=run["region"]))
            except (SourceError, ValueError):
                continue
        kept, duplicate_count = dedupe_jobs(normalized)
        if len(kept) > _MAX_JOBS_PER_RUN:
            duplicate_count += len(kept) - _MAX_JOBS_PER_RUN
            kept = kept[:_MAX_JOBS_PER_RUN]
        upsert_result = await upsert_jobs(conn, search_run_id=run_id, jobs=kept)
        await _persist_provenance(
            conn,
            run_id=run_id,
            all_jobs=kept,
            kept_jobs=kept,
            job_ids=upsert_result.job_ids,
        )
        has_downstream_work = await _enqueue_requirement_work(
            conn,
            run_id=run_id,
            jobs=kept,
            job_ids=upsert_result.job_ids,
            extraction_enabled=getattr(settings, "requirement_extraction_enabled", False),
        )

        failed_outcomes = [outcome for outcome in outcomes if outcome.status == "failed"]
        retryable_outcomes = [outcome for outcome in outcomes if outcome.retryable]
        discovered_count = sum(outcome.discovered_count for outcome in outcomes)
        duplicate_total = duplicate_count + upsert_result.duplicates
        attempts = int(item.get("attempts") or 0)
        max_attempts = getattr(settings, "max_attempts", 3)
        if retryable_outcomes and not kept and attempts < max_attempts:
            await _update_run(
                conn,
                run_id=run_id,
                status="processing",
                discovered_count=discovered_count,
                normalized_count=len(kept),
                duplicate_count=duplicate_total,
                failed_count=len(failed_outcomes),
                terminal=False,
            )
            await retry_item(conn, item_id, "retryable source failure", attempts)
            return

        if has_downstream_work:
            status = "processing"
        elif not kept:
            status = "failed"
        elif failed_outcomes:
            status = "partial"
        else:
            status = "completed"
        await _update_run(
            conn,
            run_id=run_id,
            status=status,
            discovered_count=discovered_count,
            normalized_count=len(kept),
            duplicate_count=duplicate_total,
            failed_count=len(failed_outcomes),
            terminal=not has_downstream_work,
        )
        if retryable_outcomes and not kept:
            await fail_item(conn, item_id, "retryable source failure exhausted")
        else:
            await complete_item(conn, item_id)
    except Exception:  # noqa: BLE001 - retry heterogeneous source/DB failures
        await conn.rollback()
        attempts = int(item.get("attempts") or 0)
        max_attempts = getattr(settings, "max_attempts", 3)
        if attempts >= max_attempts:
            await conn.execute(
                """
                update public.job_search_runs
                set status = 'failed', completed_at = now()
                where id = %s
                """,
                (run_id,),
            )
            await fail_item(conn, item_id, "discovery run failed")
        else:
            await conn.execute(
                """
                update public.job_search_runs
                set status = 'queued', completed_at = null
                where id = %s
                """,
                (run_id,),
            )
            await retry_item(conn, item_id, "discovery run failed", attempts)
    finally:
        if page_fetcher is not None:
            try:
                await page_fetcher.aclose()
            except Exception:  # noqa: BLE001, S110 - teardown is best effort
                pass
        if owned_sources:
            await _close_sources(sources)


__all__ = ["handle_discover_jobs"]
