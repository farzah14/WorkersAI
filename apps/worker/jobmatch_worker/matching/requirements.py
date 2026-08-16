"""Cached structured job requirement extraction through the AI router.

Requirements are extracted once per unique ``job_id + description_hash``
pair and persisted in ``public.job_requirements``. A cache hit for the
current description hash skips the generative call entirely.
"""

from typing import Any

from psycopg import AsyncConnection
from pydantic import ValidationError

from jobmatch_worker.ai.base import PermanentAiError, StructuredOutputError
from jobmatch_worker.ai.router import AiRouter
from jobmatch_worker.matching.models import JobRequirements
from jobmatch_worker.matching.prompt import (
    build_requirements_system_prompt,
    build_requirements_user_prompt,
)


def _validation_summary(exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors()[:3]:
        loc = ".".join(str(part) for part in error.get("loc", ()))
        details.append(f"{loc}: {error.get('msg', 'invalid')}")
    return "; ".join(details) if details else "invalid requirements data"


async def extract_job_requirements(job_text: str, router: AiRouter) -> JobRequirements:
    if not job_text.strip():
        raise PermanentAiError("cannot extract requirements from empty job text")
    schema: dict[str, Any] = JobRequirements.model_json_schema()
    system = build_requirements_system_prompt(schema)
    user = build_requirements_user_prompt(job_text)
    result = await router.generate_structured(system=system, user=user, schema=schema)
    try:
        return JobRequirements.model_validate(result.data)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"requirements output failed validation: {_validation_summary(exc)}"
        ) from exc


async def cached_job_requirements(
    conn: AsyncConnection[Any],
    *,
    job_id: str,
    description_hash: str,
    job_text: str,
    router: AiRouter,
) -> JobRequirements:
    cursor = await conn.execute(
        """
        select description_hash, requirements
        from public.job_requirements
        where job_id = %s
        """,
        (job_id,),
    )
    row = await cursor.fetchone()
    if row is not None and row["description_hash"] == description_hash:
        return JobRequirements.model_validate(row["requirements"])

    requirements = await extract_job_requirements(job_text, router)
    await conn.execute(
        """
        insert into public.job_requirements (job_id, description_hash, requirements)
        values (%s, %s, %s)
        on conflict (job_id) do update
        set description_hash = excluded.description_hash,
            requirements = excluded.requirements,
            extracted_at = now()
        """,
        (job_id, description_hash, requirements.model_dump(mode="json")),
    )
    return requirements


__all__ = ["cached_job_requirements", "extract_job_requirements"]