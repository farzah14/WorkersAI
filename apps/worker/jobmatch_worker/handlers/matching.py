"""Work-item handlers for job requirement extraction and hybrid matching."""

import hashlib
from typing import Any

from psycopg import AsyncConnection

from jobmatch_worker.ai.base import PermanentAiError
from jobmatch_worker.ai.router import AiAuditRecorder, AiRouter
from jobmatch_worker.config import Settings
from jobmatch_worker.handlers.profile import build_ai_providers
from jobmatch_worker.matching.requirements import cached_job_requirements
from jobmatch_worker.matching.semantic import EmbeddingClient, SemanticMatcher
from jobmatch_worker.matching.service import run_match
from jobmatch_worker.profiles.models import CandidateProfile
from jobmatch_worker.queue import complete_item, enqueue_item, fail_item, retry_item

MATCH_EXPLAIN_OPERATION = "match_explain"
REQUIREMENT_EXTRACT_OPERATION = "requirement_extract"

_RUN_SELECT_SQL = """
select r.user_id, r.candidate_profile_id, sp.locations
from public.job_search_runs r
join public.search_profiles sp on sp.id = r.search_profile_id
where r.id = %s
"""

_PROFILE_SELECT_SQL = """
select profile
from public.candidate_profiles
where id = %s and confirmed_at is not null
"""

_JOB_SELECT_SQL = "select description from public.jobs where id = %s"

_MATCH_RUNS_SQL = """
select jrj.search_run_id
from public.job_search_run_jobs jrj
join public.job_search_runs r on r.id = jrj.search_run_id
where jrj.job_id = %s
  and r.status in ('queued', 'processing', 'partial', 'completed')
  and not exists (
    select 1
    from public.job_matches m
    where m.search_run_id = jrj.search_run_id
      and m.job_id = jrj.job_id
  )
"""

_PENDING_ITEMS_SQL = """
select count(*) as pending
from public.work_items
where kind = 'match_job'
  and payload->>'search_run_id' = %s
  and status in ('queued', 'processing')
"""

_FAILED_ITEMS_SQL = """
select count(*) as failed
from public.work_items
where kind = 'match_job'
  and payload->>'search_run_id' = %s
  and status = 'failed'
"""

_RUN_COMPLETE_SQL = """
update public.job_search_runs
set status = %s, failed_count = %s, completed_at = now()
where id = %s
"""


async def _enqueue_match_items(
    conn: AsyncConnection[Any],
    *,
    job_id: str,
    description_hash: str,
) -> None:
    cursor = await conn.execute(_MATCH_RUNS_SQL, (job_id,))
    runs = await cursor.fetchall()
    for row in runs:
        run_id = str(row["search_run_id"])
        await enqueue_item(
            conn,
            kind="match_job",
            dedupe_key=f"match_job:{run_id}:{job_id}:{description_hash}",
            payload={"search_run_id": run_id, "job_id": job_id},
        )


def build_semantic_matcher(settings: Settings) -> SemanticMatcher:
    if settings.ollama_embed_model:
        client = EmbeddingClient(
            api_key=settings.ollama_api_key,
            model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
            timeout=settings.ai_timeout_seconds,
        )
    else:
        client = None
    return SemanticMatcher(client=client)


async def handle_extract_job_requirements(
    conn: AsyncConnection[Any],
    item: dict[str, Any],
    settings: Settings,
    *,
    router: AiRouter | None = None,
    audit: AiAuditRecorder | None = None,
) -> None:
    payload = item.get("payload") or {}
    job_id = payload.get("job_id")
    description_hash = payload.get("description_hash")
    item_id = str(item["id"])
    if not job_id or not description_hash:
        await fail_item(conn, item_id, "payload missing job_id or description_hash")
        return

    job_row = await conn.execute(_JOB_SELECT_SQL, (job_id,))
    job = await job_row.fetchone()
    if job is None or not job.get("description"):
        await fail_item(conn, item_id, "job not found")
        return

    owned_router = router is None
    if router is None:
        providers = build_ai_providers(settings)
        if not providers:
            await fail_item(conn, item_id, "no AI providers configured")
            return
        router = AiRouter(providers, operation=REQUIREMENT_EXTRACT_OPERATION, audit=audit)
    try:
        try:
            await cached_job_requirements(
                conn,
                job_id=job_id,
                description_hash=description_hash,
                job_text=job["description"],
                router=router,
            )
            await _enqueue_match_items(
                conn,
                job_id=str(job_id),
                description_hash=str(description_hash),
            )
            await complete_item(conn, item_id)
        except PermanentAiError as exc:
            await fail_item(conn, item_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - heterogeneous transient failures
            await conn.rollback()
            attempt = int(item.get("attempts") or 0)
            if attempt >= settings.max_attempts:
                await fail_item(conn, item_id, "requirement extraction failed")
            else:
                await retry_item(conn, item_id, str(exc), attempt)
    finally:
        if owned_router:
            await router.aclose()


async def handle_match_job(
    conn: AsyncConnection[Any],
    item: dict[str, Any],
    settings: Settings,
    *,
    router: AiRouter | None = None,
    semantic: SemanticMatcher | None = None,
    audit: AiAuditRecorder | None = None,
) -> None:
    payload = item.get("payload") or {}
    run_id = payload.get("search_run_id")
    job_id = payload.get("job_id")
    item_id = str(item["id"])
    if not run_id or not job_id:
        await fail_item(conn, item_id, "payload missing search_run_id or job_id")
        return

    run_row = await conn.execute(_RUN_SELECT_SQL, (run_id,))
    run = await run_row.fetchone()
    if run is None:
        await fail_item(conn, item_id, "search run not found")
        return

    profile_row = await conn.execute(
        _PROFILE_SELECT_SQL,
        (run["candidate_profile_id"],),
    )
    profile_result = await profile_row.fetchone()
    if profile_result is None:
        await fail_item(conn, item_id, "candidate profile not confirmed")
        return
    profile = CandidateProfile.model_validate(profile_result["profile"])

    job_row = await conn.execute(_JOB_SELECT_SQL, (job_id,))
    job = await job_row.fetchone()
    if job is None or not job.get("description"):
        await fail_item(conn, item_id, "job not found")
        return

    locations = list(run.get("locations") or [])
    description_hash = hashlib.sha256(job["description"].encode("utf-8")).hexdigest()

    owned_router = router is None
    if router is None:
        providers = build_ai_providers(settings)
        if not providers:
            await fail_item(conn, item_id, "no AI providers configured")
            return
        router = AiRouter(providers, operation=MATCH_EXPLAIN_OPERATION, audit=audit)
    if semantic is None:
        semantic = build_semantic_matcher(settings)

    try:
        try:
            await run_match(
                conn,
                user_id=run["user_id"],
                search_run_id=run_id,
                job_id=job_id,
                candidate_profile_id=run["candidate_profile_id"],
                profile=profile,
                candidate_location=locations[0] if locations else None,
                job_text=job["description"],
                description_hash=description_hash,
                router=router,
                semantic=semantic,
            )

            pending_cursor = await conn.execute(_PENDING_ITEMS_SQL, (run_id,))
            pending_result = await pending_cursor.fetchone()
            if pending_result is None:
                raise RuntimeError("work item count returned no row")
            pending = int(pending_result["pending"])
            if pending == 0:
                failed_cursor = await conn.execute(_FAILED_ITEMS_SQL, (run_id,))
                failed_result = await failed_cursor.fetchone()
                if failed_result is None:
                    raise RuntimeError("work item count returned no row")
                failed = int(failed_result["failed"])
                await conn.execute(
                    _RUN_COMPLETE_SQL,
                    ("completed" if failed == 0 else "partial", failed, run_id),
                )
            await complete_item(conn, item_id)
        except PermanentAiError as exc:
            await fail_item(conn, item_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - heterogeneous transient failures
            await conn.rollback()
            attempt = int(item.get("attempts") or 0)
            if attempt >= settings.max_attempts:
                await fail_item(conn, item_id, "job match failed")
            else:
                await retry_item(conn, item_id, str(exc), attempt)
    finally:
        if owned_router:
            await router.aclose()


__all__ = [
    "MATCH_EXPLAIN_OPERATION",
    "REQUIREMENT_EXTRACT_OPERATION",
    "build_semantic_matcher",
    "handle_extract_job_requirements",
    "handle_match_job",
]
