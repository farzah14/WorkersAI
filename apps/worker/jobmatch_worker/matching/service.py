"""Hybrid deterministic + semantic matching pipeline.

The pipeline loads verified candidate facts and cached structured job
requirements, evaluates satisfaction per dimension (exact first, then
semantic similarity with deterministic lexical fallback), computes the
weighted deterministic scores, derives strengths/gaps/critical gaps and
the verdict, asks the router for an explanation and recommendations, and
finally sanitizes recommendations against verified facts before upserting
the match row. The LLM never decides the final score.
"""

import re
from dataclasses import dataclass
from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from jobmatch_worker.ai.base import PermanentAiError, StructuredOutputError
from jobmatch_worker.ai.router import AiRouter
from jobmatch_worker.matching.models import Category, JobRequirement
from jobmatch_worker.matching.recommendations import (
    build_explanation_input,
    sanitize_recommendations,
)
from jobmatch_worker.matching.requirements import cached_job_requirements
from jobmatch_worker.matching.scoring import (
    combine_dimension_scores,
    find_critical_gaps,
    score_dimension,
    verdict_for,
)
from jobmatch_worker.matching.semantic import SemanticMatcher, SemanticMatchResult
from jobmatch_worker.profiles.models import CandidateProfile

SEMANTIC_MATCH_THRESHOLD = 0.75

_EXPERIENCE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(years?|months?|yrs?|mos?)?\b"
)
_CATEGORIES: tuple[Category, ...] = (
    "skill",
    "experience",
    "education",
    "location",
    "seniority",
    "language",
)
_DIMENSION_KEYS: dict[Category, str] = {
    "skill": "skills",
    "experience": "experience",
    "education": "education",
    "location": "location",
    "seniority": "seniority",
    "language": "language",
}


@dataclass(frozen=True, slots=True)
class MatchOutcome:
    dimension_scores: dict[str, int]
    overall_score: int
    strengths: list[str]
    gaps: list[str]
    critical_gaps: list[JobRequirement]
    verdict: str
    semantic_degraded: bool = False


@dataclass(frozen=True, slots=True)
class MatchResult:
    user_id: str
    search_run_id: str
    candidate_profile_id: str
    job_id: str
    dimension_scores: dict[str, int]
    overall_score: int
    strengths: list[str]
    gaps: list[str]
    critical_gaps: list[JobRequirement]
    verdict: str
    explanation: str
    recommendations: list[str]
    semantic_degraded: bool


def _candidate_terms(profile: CandidateProfile) -> set[str]:
    values: list[str] = list(profile.skills) + list(profile.languages) + list(profile.education)
    values.extend(profile.target_roles)
    if profile.current_role:
        values.append(profile.current_role)
    if profile.name:
        values.append(profile.name)
    return {
        token.casefold()
        for value in values
        for token in re.findall(r"[a-z0-9.+#-]+", value.casefold())
    }


def _terms(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9.+#-]+", value.casefold()))


def _experience_satisfied(value: str, experience_years: float | None) -> bool:
    if experience_years is not None:
        match = _EXPERIENCE_RE.search(value)
        if match:
            number = float(match.group(1))
            unit = match.group(2)
            if unit and unit.startswith(("month", "mos")):
                return experience_years * 12 >= number
            return experience_years >= number
    if experience_years is None:
        return False
    return _terms(value) <= _terms(f"{int(experience_years)} years")


def _exact_matched(
    category: Category,
    values: list[str],
    profile: CandidateProfile,
    candidate_location: str | None,
) -> set[str]:
    matched: set[str] = set()
    for value in values:
        if category == "experience" and _experience_satisfied(value, profile.experience_years) or (
            category == "seniority"
            and profile.seniority != "unknown"
            and value.casefold() == profile.seniority
        ) or category == "location" and candidate_location and _terms(value) <= _terms(candidate_location) or (
            category in ("skill", "education", "language")
            and _terms(value) <= _candidate_terms(profile)
        ):
            matched.add(value)
    return matched


def _statements_for(
    category: Category,
    profile: CandidateProfile,
    candidate_location: str | None,
) -> list[str]:
    if category == "skill":
        return list(profile.skills)
    if category == "experience":
        if profile.experience_years is None:
            return []
        return [f"{profile.experience_years:g} years of experience"]
    if category == "education":
        return list(profile.education)
    if category == "location":
        return [candidate_location] if candidate_location else []
    if category == "seniority":
        return [profile.seniority] if profile.seniority != "unknown" else []
    return list(profile.languages)


def _requirements_by_category(
    requirements: list[JobRequirement],
) -> dict[Category, list[JobRequirement]]:
    grouped: dict[Category, list[JobRequirement]] = {category: [] for category in _CATEGORIES}
    for requirement in requirements:
        grouped[requirement.category].append(requirement)
    return grouped


async def compute_match_outcome(
    profile: CandidateProfile,
    candidate_location: str | None,
    requirements: list[JobRequirement],
    semantic: SemanticMatcher,
) -> MatchOutcome:
    grouped = _requirements_by_category(requirements)
    dimension_scores: dict[str, int] = {}
    matched_all: set[str] = set()
    semantically_matched_all: set[str] = set()
    degraded = False
    for category in _CATEGORIES:
        category_requirements = grouped[category]
        values = [r.value for r in category_requirements]
        exact = _exact_matched(category, values, profile, candidate_location)
        semantic_match: SemanticMatchResult | None = None
        statements = _statements_for(category, profile, candidate_location)
        if statements and values:
            semantic_match = await semantic.match(
                candidate_statements=statements,
                requirement_values=values,
            )
            degraded = degraded or semantic_match.degraded
        semantically_matched = (
            {
                value
                for value in values
                if value not in exact
                and semantic_match is not None
                and semantic_match.scores.get(value, 0.0) >= SEMANTIC_MATCH_THRESHOLD
            }
            if semantic_match is not None
            else set()
        )
        matched_all.update(exact)
        matched_all.update(semantically_matched)
        semantically_matched_all.update(semantically_matched)
        dimension_scores[_DIMENSION_KEYS[category]] = score_dimension(
            category_requirements,
            exact,
            semantically_matched,
        )

    overall = combine_dimension_scores(dimension_scores)
    critical_gaps = find_critical_gaps(requirements, matched_all, semantically_matched_all)
    strengths = [
        r.value
        for r in requirements
        if r.value in matched_all and r.criticality in ("must", "preferred")
    ]
    gaps = [
        r.value
        for r in requirements
        if r.value not in matched_all and r.criticality != "must"
    ]
    return MatchOutcome(
        dimension_scores=dimension_scores,
        overall_score=overall,
        strengths=strengths,
        gaps=gaps,
        critical_gaps=critical_gaps,
        verdict=verdict_for(overall, critical_gap=bool(critical_gaps)),
        semantic_degraded=degraded,
    )


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    explanation: str
    recommendations: list[str]


async def explain_match(
    router: AiRouter,
    profile: CandidateProfile,
    requirements: list[JobRequirement],
    outcome: MatchOutcome,
) -> ExplanationResult:
    payload = build_explanation_input(
        candidate=profile,
        requirements=requirements,
        dimension_scores=outcome.dimension_scores,
        strengths=outcome.strengths,
        gaps=outcome.gaps,
        critical_gaps=[g.value for g in outcome.critical_gaps],
    )
    result = await router.generate_structured(
        system=(
            "You explain an automated job match. The dimension scores you receive "
            "are authoritative and must not be changed. Never invent candidate "
            "facts: recommendations must be grounded in the candidate profile."
        ),
        user=(
            "Return a JSON object with exactly two fields: "
            '"explanation" (a concise string of 1-3 sentences) and '
            '"recommendations" (an array of 1-5 concrete strings). '
            f"Facts:\n{_as_json(payload)}"
        ),
        schema={
            "type": "object",
            "properties": {
                "explanation": {"type": "string", "minLength": 1},
                "recommendations": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                    "minItems": 1,
                    "maxItems": 5,
                },
            },
            "required": ["explanation", "recommendations"],
            "additionalProperties": False,
        },
    )
    data = result.data
    explanation = data.get("explanation")
    recommendations = data.get("recommendations")
    if not isinstance(explanation, str) or not explanation.strip():
        raise StructuredOutputError("explanation output failed validation: explanation")
    if not isinstance(recommendations, list) or not recommendations:
        raise StructuredOutputError("explanation output failed validation: recommendations")
    if not all(isinstance(item, str) and item.strip() for item in recommendations):
        raise StructuredOutputError("explanation output failed validation: recommendation item")
    sanitized = sanitize_recommendations(profile, recommendations)
    return ExplanationResult(explanation=explanation.strip(), recommendations=sanitized)


def _as_json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


UPSERT_MATCH_SQL = """
insert into public.job_matches
    (user_id, search_run_id, candidate_profile_id, job_id,
     overall_score, skills_score, experience_score, education_score,
     location_score, seniority_score, language_score,
     strengths, gaps, critical_gaps, verdict, explanation, recommendations,
     semantic_degraded)
values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
on conflict (search_run_id, job_id) do update
set user_id = excluded.user_id,
    candidate_profile_id = excluded.candidate_profile_id,
    overall_score = excluded.overall_score,
    skills_score = excluded.skills_score,
    experience_score = excluded.experience_score,
    education_score = excluded.education_score,
    location_score = excluded.location_score,
    seniority_score = excluded.seniority_score,
    language_score = excluded.language_score,
    strengths = excluded.strengths,
    gaps = excluded.gaps,
    critical_gaps = excluded.critical_gaps,
    verdict = excluded.verdict,
    explanation = excluded.explanation,
    recommendations = excluded.recommendations,
    semantic_degraded = excluded.semantic_degraded
"""


async def run_match(
    conn: AsyncConnection[Any],
    *,
    user_id: str,
    search_run_id: str,
    job_id: str,
    candidate_profile_id: str,
    profile: CandidateProfile,
    candidate_location: str | None,
    job_text: str,
    description_hash: str,
    router: AiRouter,
    semantic: SemanticMatcher,
) -> MatchResult:
    if not job_text.strip():
        raise PermanentAiError("cannot match an empty job description")
    requirements = await cached_job_requirements(
        conn,
        job_id=job_id,
        description_hash=description_hash,
        job_text=job_text,
        router=router,
    )
    outcome = await compute_match_outcome(
        profile,
        candidate_location,
        requirements.requirements,
        semantic,
    )
    explanation_result = await explain_match(router, profile, requirements.requirements, outcome)
    await conn.execute(
        UPSERT_MATCH_SQL,
        (
            user_id,
            search_run_id,
            candidate_profile_id,
            job_id,
            outcome.overall_score,
            outcome.dimension_scores["skills"],
            outcome.dimension_scores["experience"],
            outcome.dimension_scores["education"],
            outcome.dimension_scores["location"],
            outcome.dimension_scores["seniority"],
            outcome.dimension_scores["language"],
            Jsonb(outcome.strengths),
            Jsonb(outcome.gaps),
            Jsonb([g.value for g in outcome.critical_gaps]),
            outcome.verdict,
            explanation_result.explanation,
            Jsonb(explanation_result.recommendations),
            outcome.semantic_degraded,
        ),
    )
    return MatchResult(
        user_id=user_id,
        search_run_id=search_run_id,
        candidate_profile_id=candidate_profile_id,
        job_id=job_id,
        dimension_scores=outcome.dimension_scores,
        overall_score=outcome.overall_score,
        strengths=outcome.strengths,
        gaps=outcome.gaps,
        critical_gaps=outcome.critical_gaps,
        verdict=outcome.verdict,
        explanation=explanation_result.explanation,
        recommendations=explanation_result.recommendations,
        semantic_degraded=outcome.semantic_degraded,
    )


__all__ = [
    "SEMANTIC_MATCH_THRESHOLD",
    "ExplanationResult",
    "MatchOutcome",
    "MatchResult",
    "compute_match_outcome",
    "explain_match",
    "run_match",
]
