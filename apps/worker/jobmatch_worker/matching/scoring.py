"""Deterministic, explainable match scoring.

Scores are computed from candidate facts and extracted job requirements
with explicit weights; the LLM never decides the final number. A missing
``must`` requirement is the only source of a critical gap, and any critical
gap caps the verdict at ``not_recommended``.
"""

from collections.abc import Mapping

from jobmatch_worker.matching.models import JobRequirement

DEFAULT_WEIGHTS: dict[str, float] = {
    "skills": 0.35,
    "experience": 0.25,
    "seniority": 0.15,
    "education": 0.10,
    "language": 0.08,
    "location": 0.07,
}

CRITICALITY_WEIGHT: dict[str, int] = {
    "must": 5,
    "preferred": 2,
    "nice": 1,
}

EXACT_MATCH_SCORE = 1.0
SEMANTIC_MATCH_SCORE = 0.85
ABSENT_MATCH_SCORE = 0.0


def combine_dimension_scores(scores: Mapping[str, int]) -> int:
    return round(sum(scores[k] * DEFAULT_WEIGHTS[k] for k in DEFAULT_WEIGHTS))


def verdict_for(score: int, *, critical_gap: bool) -> str:
    if critical_gap:
        return "not_recommended"
    if score >= 90:
        return "highly_recommended"
    if score >= 80:
        return "recommended"
    if score >= 70:
        return "potential"
    return "low_match"


def score_dimension(
    requirements: list[JobRequirement],
    matched: set[str],
    semantically_matched: set[str] | None = None,
) -> int:
    """Score one dimension from verified and semantic-equivalent matches.

    Exact verified matches score 1.0, semantic-equivalent matches score
    0.85, unknown/absent matches score 0.0. Within the dimension,
    ``must`` requirements weigh 5, ``preferred`` 2, and ``nice`` 1.
    A dimension with no requirements is neutral (100) so it never drags
    the overall score down.
    """
    if not requirements:
        return 100
    semantic = semantically_matched or set()
    total = 0.0
    weight_sum = 0
    for req in requirements:
        weight = CRITICALITY_WEIGHT[req.criticality]
        weight_sum += weight
        key = req.value.casefold()
        if key in matched:
            quality = EXACT_MATCH_SCORE
        elif key in semantic:
            quality = SEMANTIC_MATCH_SCORE
        else:
            quality = ABSENT_MATCH_SCORE
        total += weight * quality
    return round(100 * total / weight_sum)


def find_critical_gaps(
    requirements: list[JobRequirement],
    matched: set[str],
    semantically_matched: set[str] | None = None,
) -> list[JobRequirement]:
    semantic = semantically_matched or set()
    return [
        req
        for req in requirements
        if req.criticality == "must"
        and req.value.casefold() not in matched
        and req.value.casefold() not in semantic
    ]


__all__ = [
    "ABSENT_MATCH_SCORE",
    "CRITICALITY_WEIGHT",
    "DEFAULT_WEIGHTS",
    "EXACT_MATCH_SCORE",
    "SEMANTIC_MATCH_SCORE",
    "combine_dimension_scores",
    "find_critical_gaps",
    "score_dimension",
    "verdict_for",
]