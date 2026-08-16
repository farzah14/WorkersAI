import json
import pathlib

import pytest

from jobmatch_worker.matching.models import JobRequirement
from jobmatch_worker.matching.semantic import SemanticMatcher
from jobmatch_worker.matching.service import MatchOutcome, compute_match_outcome
from jobmatch_worker.profiles.models import CandidateProfile

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


def bucket_for(outcome: MatchOutcome) -> str:
    if outcome.critical_gaps:
        return "not_recommended"
    if outcome.overall_score >= 80:
        return "best"
    if outcome.overall_score >= 70:
        return "strong"
    if outcome.overall_score >= 50:
        return "potential"
    return "low"


def load_fixture(name: str) -> dict:
    path = GOLDEN_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "fixture_name",
    ["high_match", "medium_match", "low_match"],
)
@pytest.mark.asyncio
async def test_golden_bucket_is_stable(fixture_name: str) -> None:
    data = load_fixture(fixture_name)
    profile = CandidateProfile.model_validate(data["candidate"])
    requirements = [JobRequirement.model_validate(r) for r in data["requirements"]]
    outcome = await compute_match_outcome(
        profile,
        data.get("candidate_location"),
        requirements,
        SemanticMatcher(client=None),
    )
    assert bucket_for(outcome) == data["expected_bucket"]


@pytest.mark.asyncio
async def test_critical_language_gap_forced_not_recommended() -> None:
    data = load_fixture("medium_match")
    assert data["expected_bucket"] == "not_recommended"
    profile = CandidateProfile.model_validate(data["candidate"])
    requirements = [JobRequirement.model_validate(r) for r in data["requirements"]]
    outcome = await compute_match_outcome(
        profile,
        data.get("candidate_location"),
        requirements,
        SemanticMatcher(client=None),
    )
    assert bucket_for(outcome) == "not_recommended"
    language_gaps = [g.value for g in outcome.critical_gaps if g.value == "Japanese"]
    assert language_gaps
    assert outcome.overall_score >= 70
    assert outcome.dimension_scores["skills"] >= 85