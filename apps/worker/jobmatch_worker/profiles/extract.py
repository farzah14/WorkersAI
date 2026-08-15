"""Schema-valid candidate profile extraction through the AI router."""

from typing import Any

from pydantic import ValidationError

from jobmatch_worker.ai.base import PermanentAiError, StructuredOutputError
from jobmatch_worker.ai.router import AiRouter
from jobmatch_worker.profiles.models import CandidateProfile
from jobmatch_worker.profiles.prompt import (
    build_profile_system_prompt,
    build_profile_user_prompt,
)


def _validation_summary(exc: ValidationError) -> str:
    details: list[str] = []
    for error in exc.errors()[:3]:
        loc = ".".join(str(part) for part in error.get("loc", ()))
        details.append(f"{loc}: {error.get('msg', 'invalid')}")
    return "; ".join(details) if details else "invalid profile data"


async def extract_candidate_profile(cv_text: str, router: AiRouter) -> CandidateProfile:
    if not cv_text.strip():
        raise PermanentAiError("cannot extract a profile from empty CV text")
    schema: dict[str, Any] = CandidateProfile.model_json_schema()
    system = build_profile_system_prompt(schema)
    user = build_profile_user_prompt(cv_text)
    result = await router.generate_structured(system=system, user=user, schema=schema)
    try:
        return CandidateProfile.model_validate(result.data)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"profile output failed validation: {_validation_summary(exc)}"
        ) from exc


__all__ = ["extract_candidate_profile"]