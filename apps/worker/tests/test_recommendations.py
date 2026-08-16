from jobmatch_worker.matching.models import JobRequirement
from jobmatch_worker.matching.recommendations import (
    build_explanation_input,
    sanitize_recommendations,
)
from jobmatch_worker.profiles.models import CandidateProfile


def test_recommendations_cannot_add_unverified_skill() -> None:
    candidate = {"skills": ["Python", "SQL"]}
    rec = sanitize_recommendations(candidate, ["Add 3 years AWS experience", "Highlight SQL optimization work"])
    assert "AWS" not in " ".join(rec)
    assert any("SQL" in x for x in rec)


def test_recommendation_grounded_in_verified_skill_is_kept() -> None:
    candidate = {"skills": ["Python", "SQL"]}
    rec = sanitize_recommendations(candidate, ["Lead a Python project end to end"])
    assert rec == ["Lead a Python project end to end"]


def test_unverified_certification_and_degree_claims_dropped() -> None:
    candidate = {"skills": ["Python"], "education": ["BSc Computer Science"]}
    rec = sanitize_recommendations(
        candidate,
        [
            "Add an AWS certification",
            "Mention your MBA degree",
            "Highlight your computer science degree",
        ],
    )
    assert all("AWS" not in x and "MBA" not in x for x in rec)
    assert any("computer science" in x for x in rec)


def test_unverified_employer_claim_dropped() -> None:
    candidate = {"skills": ["Python"], "current_role": "Data Engineer"}
    rec = sanitize_recommendations(candidate, ["Describe your work at AcmeCorp", "Describe your data engineering work"])
    assert all("AcmeCorp" not in x for x in rec)
    assert any("data engineering" in x for x in rec)


def test_unverified_experience_converted_to_conditional_phrasing() -> None:
    candidate = {"skills": ["Python"]}
    rec = sanitize_recommendations(candidate, ["Add 3 years AWS experience"])
    assert rec
    assert any("If you have" in x for x in rec)
    assert all("AWS" not in x and "3 years" not in x for x in rec)


def test_language_claim_guarded() -> None:
    candidate = {"skills": ["Python"], "languages": ["Bahasa Indonesia"]}
    rec = sanitize_recommendations(candidate, ["List Japanese proficiency", "List Bahasa Indonesia proficiency"])
    assert all("Japanese" not in x for x in rec)
    assert any("Bahasa Indonesia" in x for x in rec)


def test_empty_recommendations_passthrough() -> None:
    assert sanitize_recommendations({"skills": ["Python"]}, []) == []


def test_guard_accepts_verified_candidate_profile_object() -> None:
    candidate = CandidateProfile(
        target_roles=["Data Engineer"],
        skills=["Python"],
        experience_years=4.0,
    )
    rec = sanitize_recommendations(
        candidate,
        ["Highlight your 4 years of experience", "Add 10 years of Python experience"],
    )
    assert any("4 years" in x for x in rec)
    assert all("10 years" not in x for x in rec)


def test_build_explanation_input_contains_structured_facts_only() -> None:
    candidate = CandidateProfile(
        target_roles=["Data Engineer"],
        skills=["Python", "SQL"],
        experience_years=4.0,
    )
    requirements = [
        JobRequirement(
            category="skill",
            value="Python",
            criticality="must",
            evidence="Strong Python required",
        )
    ]
    result = build_explanation_input(
        candidate=candidate,
        requirements=requirements,
        dimension_scores={"skills": 90, "experience": 80},
        strengths=["Python"],
        gaps=["AWS"],
        critical_gaps=["AWS"],
    )
    assert result["candidate_profile"]["skills"] == ["Python", "SQL"]
    assert result["job_requirements"][0]["value"] == "Python"
    assert result["dimension_scores"] == {"skills": 90, "experience": 80}
    assert result["strengths"] == ["Python"]
    assert result["critical_gaps"] == ["AWS"]
    assert "authoritative" in result["instruction"]
    assert "full_text" not in json_dumps(result)
    assert "description" not in json_dumps(result)


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value)