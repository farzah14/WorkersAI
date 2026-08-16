from __future__ import annotations

import pytest

from jobmatch_worker.matching.models import JobRequirement
from jobmatch_worker.matching.scoring import (
    DEFAULT_WEIGHTS,
    combine_dimension_scores,
    find_critical_gaps,
    score_dimension,
    verdict_for,
)


def test_default_weights_follow_approved_dimensions() -> None:
    assert DEFAULT_WEIGHTS == {
        "skills": 0.35,
        "experience": 0.25,
        "seniority": 0.15,
        "education": 0.10,
        "language": 0.08,
        "location": 0.07,
    }


def test_default_weights_sum_to_one() -> None:
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_default_weighted_score() -> None:
    score = combine_dimension_scores(
        {
            "skills": 90,
            "experience": 80,
            "education": 100,
            "location": 100,
            "seniority": 80,
            "language": 100,
        }
    )
    assert score == 88


def test_critical_gap_caps_verdict() -> None:
    assert verdict_for(92, critical_gap=True) == "not_recommended"


def test_verdict_thresholds() -> None:
    assert verdict_for(95, critical_gap=False) == "highly_recommended"
    assert verdict_for(90, critical_gap=False) == "highly_recommended"
    assert verdict_for(85, critical_gap=False) == "recommended"
    assert verdict_for(75, critical_gap=False) == "potential"
    assert verdict_for(60, critical_gap=False) == "low_match"


def test_dimension_score_full_exact_match() -> None:
    reqs = [
        JobRequirement(category="skill", value="Python", criticality="must", evidence="Python required"),
        JobRequirement(category="skill", value="SQL", criticality="must", evidence="SQL required"),
    ]
    assert score_dimension(reqs, matched={"python", "sql"}) == 100


def test_dimension_score_semantic_match_is_085() -> None:
    reqs = [
        JobRequirement(category="skill", value="Python", criticality="must", evidence="Python required"),
    ]
    assert score_dimension(reqs, matched=set(), semantically_matched={"python"}) == 85


def test_dimension_score_absent_requirement_is_zero() -> None:
    reqs = [
        JobRequirement(category="skill", value="Python", criticality="must", evidence="Python required"),
        JobRequirement(category="skill", value="AWS", criticality="must", evidence="AWS required"),
    ]
    assert score_dimension(reqs, matched={"python"}) == 50


def test_dimension_weights_must_preferred_nice() -> None:
    reqs = [
        JobRequirement(category="skill", value="AWS", criticality="must", evidence="AWS required"),
        JobRequirement(category="skill", value="Python", criticality="preferred", evidence="Python preferred"),
        JobRequirement(category="skill", value="Go", criticality="nice", evidence="Go is a plus"),
    ]
    assert score_dimension(reqs, matched={"python"}) == 25
    assert score_dimension(reqs, matched={"aws", "go"}) == 75


def test_dimension_score_empty_requirements_is_neutral() -> None:
    assert score_dimension([], matched=set()) == 100


def test_critical_gap_only_for_missing_must() -> None:
    reqs = [
        JobRequirement(category="skill", value="Python", criticality="must", evidence="Python required"),
        JobRequirement(category="skill", value="AWS", criticality="nice", evidence="AWS is a plus"),
    ]
    gaps = find_critical_gaps(reqs, matched={"python"})
    assert [g.value for g in gaps] == []


def test_find_critical_gaps_lists_missing_must_with_evidence() -> None:
    reqs = [
        JobRequirement(category="skill", value="Python", criticality="must", evidence="Python required"),
        JobRequirement(category="skill", value="AWS", criticality="must", evidence="AWS required"),
        JobRequirement(category="skill", value="Go", criticality="nice", evidence="Go is a plus"),
    ]
    gaps = find_critical_gaps(reqs, matched={"python"})
    assert [g.value for g in gaps] == ["AWS"]
    assert gaps[0].evidence == "AWS required"