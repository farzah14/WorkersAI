"""Orchestrate resilient job discovery runs."""

from __future__ import annotations

import asyncio
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
from jobmatch_worker.jobs.connectors.greenhouse import GreenhouseConnector
from jobmatch_worker.jobs.connectors.lever import LeverConnector
from jobmatch_worker.jobs.connectors.tavily import TavilyConnector
from jobmatch_worker.jobs.dedupe import (
    dedupe_jobs,
    is_fuzzy_duplicate,
    job_fingerprint,
    upsert_jobs,
)
from jobmatch_worker.jobs.indonesia import (
    is_indonesia_eligible,
    is_trusted_job_url,
    parse_extra_trusted_domains,
    rank_indonesia_candidates,
    rank_indonesia_jobs,
)
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.normalize import NormalizedJob, normalize_job
from jobmatch_worker.jobs.query import SearchQuery, build_queries
from jobmatch_worker.matching.cache_key import (
    MAX_REQUIREMENT_TEXT_CHARS,
    requirements_cache_key,
)
from jobmatch_worker.queue import complete_item, enqueue_item, fail_item, retry_item

_SOURCE_CONCURRENCY = 4
_MAX_SOURCE_RESULTS = 200
_MAX_CAREER_CANDIDATES = 120
_MAX_JOBS_PER_RUN = 5
_MAX_TITLE_CHARS = 300
_MAX_COMPANY_CHARS = 300
_MAX_LOCATION_CHARS = 300
_MAX_DESCRIPTION_CHARS = MAX_REQUIREMENT_TEXT_CHARS
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
    return {
        "tavily": TavilyConnector(api_key=settings.tavily_api_key),
        "greenhouse": GreenhouseConnector(
            board_token=settings.greenhouse_board_token
        ),
        "lever": LeverConnector(site_name=settings.lever_site_name),
    }


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
    *,
    require_specific: bool = False,
) -> DiscoveredJob | None:
    content = await fetch_page(candidate.url)
    text = content.text.strip()
    if not text:
        raise SourceDataError("career_page", "empty page text")
    if content.is_closed:
        raise SourceDataError(source_key, "job page is closed")
    if require_specific and not content.is_job_posting:
        raise SourceDataError(source_key, "page is not a specific job posting")
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
    *,
    candidate_limit: int = _MAX_CAREER_CANDIDATES,
    require_specific: bool = False,
    trusted_domains: frozenset[str] | None = None,
    roles: tuple[str, ...] = (),
    locations: tuple[str, ...] = (),
    deadline_seconds: float | None = None,
) -> _SourceOutcome:
    jobs: list[DiscoveredJob] = []
    discovered_count = 0
    candidate_failures = 0
    candidate_retryable = False
    seen_candidates: set[str] = set()
    seen_job_urls: set[str] = set()
    candidates: list[DiscoveryCandidateUrl] = []
    loop = asyncio.get_running_loop()
    deadline = loop.time() + deadline_seconds if deadline_seconds is not None else None

    def remaining_seconds() -> float | None:
        if deadline is None:
            return None
        return max(0.0, deadline - loop.time())

    try:
        async with semaphore:
            for query in _queries_for_source(source_key, queries):
                remaining = remaining_seconds()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError
                if remaining is None:
                    results = await connector.search(query)
                else:
                    async with asyncio.timeout(remaining):
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
                        if trusted_domains is not None and not is_trusted_job_url(
                            result.url, trusted_domains
                        ):
                            continue
                        if len(seen_candidates) >= _MAX_CAREER_CANDIDATES:
                            raise SourceDataError(
                                source_key, "career-page candidate limit exceeded"
                            )
                        seen_candidates.add(candidate_url)
                        candidates.append(result)
                    else:
                        _validate_job_size(result, source_key)
                        canonical_url = canonicalize_url(
                            result.original_url, source_key=source_key
                        )
                        if canonical_url in seen_job_urls:
                            continue
                        seen_job_urls.add(canonical_url)
                        jobs.append(result)

            if require_specific:
                candidates = rank_indonesia_candidates(
                    candidates,
                    roles=roles,
                    locations=locations,
                )[:candidate_limit]

            candidate_semaphore = asyncio.Semaphore(_SOURCE_CONCURRENCY)
            page_fetch = fetch_page

            async def fetch_candidate(
                candidate: DiscoveryCandidateUrl,
            ) -> DiscoveredJob | None:
                if page_fetch is None:
                    return None
                async with candidate_semaphore:
                    return await _candidate_to_job(
                        candidate,
                        page_fetch,
                        source_key,
                        require_specific=require_specific,
                    )

            tasks = [asyncio.create_task(fetch_candidate(candidate)) for candidate in candidates]
            done: set[asyncio.Task[DiscoveredJob | None]] = set()
            pending: set[asyncio.Task[DiscoveredJob | None]] = set()
            if tasks:
                remaining = remaining_seconds()
                done, pending = await asyncio.wait(tasks, timeout=remaining)
            if pending:
                candidate_failures += len(pending)
                candidate_retryable = True
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

            for task in tasks:
                if task not in done:
                    continue
                try:
                    job = task.result()
                except SourceUnavailable:
                    candidate_failures += 1
                    candidate_retryable = True
                    continue
                except SourceError:
                    candidate_failures += 1
                    continue
                if job is not None:
                    jobs.append(job)
    except TimeoutError:
        return _SourceOutcome(
            source_key=source_key,
            status="failed",
            jobs=tuple(jobs),
            error_code="unavailable",
            discovered_count=discovered_count,
            retryable=True,
        )
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
            continue
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
        description_hash = requirements_cache_key(job.description)
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
        indonesia_mode = str(run["region"]).casefold() == "indonesia"
        extra_trusted_domains = parse_extra_trusted_domains(
            getattr(settings, "indonesia_trusted_job_domains", "")
        )
        outcomes = await asyncio.gather(
            *(
                _run_source(
                    source_key,
                    source,
                    queries,
                    fetch_page,
                    semaphore,
                    candidate_limit=20 if indonesia_mode else _MAX_CAREER_CANDIDATES,
                    require_specific=indonesia_mode,
                    trusted_domains=(
                        extra_trusted_domains
                        if indonesia_mode and source_key == "tavily"
                        else None
                    ),
                    roles=tuple(run["target_roles"]),
                    locations=tuple(run["locations"]),
                    deadline_seconds=60.0 if indonesia_mode else None,
                )
                for source_key, source in sources.items()
            )
        )
        for outcome in outcomes:
            await _record_source(conn, run_id=run_id, outcome=outcome)

        all_jobs = [job for outcome in outcomes for job in outcome.jobs]
        if indonesia_mode:
            all_jobs = rank_indonesia_jobs(
                [job for job in all_jobs if is_indonesia_eligible(job)],
                roles=tuple(run["target_roles"]),
                locations=tuple(run["locations"]),
                work_modes=tuple(run["work_modes"] or ()),
            )
        normalized: list[NormalizedJob] = []
        for job in all_jobs:
            try:
                normalized.append(normalize_job(job, region=run["region"]))
            except (SourceError, ValueError):
                continue
        kept, duplicate_count = dedupe_jobs(normalized)
        kept = kept[:_MAX_JOBS_PER_RUN]
        upsert_result = await upsert_jobs(conn, search_run_id=run_id, jobs=kept)
        await _persist_provenance(
            conn,
            run_id=run_id,
            all_jobs=normalized,
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
            status = "completed" if indonesia_mode and not failed_outcomes else "failed"
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
