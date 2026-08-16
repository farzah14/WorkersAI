from __future__ import annotations

from typing import Any

import pytest

from jobmatch_worker.ai.base import AiResult
from jobmatch_worker.matching.models import JobRequirement
from jobmatch_worker.matching.semantic import SemanticMatcher
from jobmatch_worker.matching.service import run_match
from jobmatch_worker.profiles.models import CandidateProfile

CANDIDATE = CandidateProfile(
    name="Rina",
    current_role="Data Engineer",
    seniority="mid",
    target_roles=["Data Engineer"],
    skills=["Python", "SQL"],
    experience_years=4.0,
    languages=["Bahasa Indonesia"],
    education=["BSc Computer Science"],
)

REQUIREMENTS = [
    JobRequirement(category="skill", value="Python", criticality="must", evidence="Python required"),
    JobRequirement(category="skill", value="SQL", criticality="must", evidence="SQL required"),
    JobRequirement(category="skill", value="AWS", criticality="nice", evidence="AWS is a plus"),
    JobRequirement(category="experience", value="3+ years", criticality="must", evidence="3+ years required"),
    JobRequirement(category="location", value="Jakarta", criticality="preferred", evidence="Jakarta preferred"),
    JobRequirement(category="language", value="Bahasa Indonesia", criticality="preferred", evidence="Bahasa preferred"),
    JobRequirement(category="seniority", value="mid", criticality="nice", evidence="Mid level"),
]


class _Cursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row


class _Connection:
    def __init__(self, requirements_row: dict[str, Any] | None = None) -> None:
        self.requirements_row = requirements_row
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> _Cursor:
        self.executed.append((query, params))
        lowered = query.lower()
        if "from public.job_requirements" in lowered:
            return _Cursor(self.requirements_row)
        return _Cursor(None)


class _FakeRouter:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data
        self.calls: list[tuple[str, str]] = []

    async def generate_structured(
        self, *, system: str, user: str, schema: dict[str, Any]
    ) -> AiResult:
        self.calls.append((system, user))
        return AiResult(provider="fake", model="fake", data=self._data, latency_ms=1)


def _requirements_json() -> dict[str, Any]:
    return {"requirements": [r.model_dump(mode="json") for r in REQUIREMENTS]}


def _explanation_data() -> dict[str, Any]:
    return {
        "explanation": "Strong match on Python and SQL.",
        "recommendations": [
            "Highlight Python projects end to end",
            "Add 3 years AWS experience",
        ],
    }


@pytest.mark.asyncio
async def test_match_run_persists_upserted_result() -> None:
    connection = _Connection(
        requirements_row={
            "description_hash": "h1",
            "requirements": _requirements_json(),
        }
    )
    router = _FakeRouter(_explanation_data())
    semantic = SemanticMatcher(client=None)

    result = await run_match(
        connection,
        user_id="user-1",
        search_run_id="run-1",
        job_id="job-1",
        candidate_profile_id="prof-1",
        profile=CANDIDATE,
        candidate_location="Jakarta, Indonesia",
        job_text="Python required",
        description_hash="h1",
        router=router,
        semantic=semantic,
    )

    assert result.overall_score >= 80
    assert "AWS" in result.gaps
    assert result.verdict != "not_recommended"
    assert result.strengths == [
        "Python",
        "SQL",
        "3+ years",
        "Jakarta",
        "Bahasa Indonesia",
    ]
    assert result.critical_gaps == []
    assert "AWS" not in " ".join(result.recommendations)
    assert result.semantic_degraded is True

    upserts = [
        params
        for query, params in connection.executed
        if "insert into public.job_matches" in query.lower() and "on conflict" in query.lower()
    ]
    assert len(upserts) == 1
    assert upserts[0][:5] == ("user-1", "run-1", "prof-1", "job-1", 97)


@pytest.mark.asyncio
async def test_second_invocation_upserts_instead_of_duplicating() -> None:
    connection = _Connection(
        requirements_row={
            "description_hash": "h1",
            "requirements": _requirements_json(),
        }
    )
    router = _FakeRouter(_explanation_data())
    semantic = SemanticMatcher(client=None)

    first = await run_match(
        connection,
        user_id="user-1",
        search_run_id="run-1",
        job_id="job-1",
        candidate_profile_id="prof-1",
        profile=CANDIDATE,
        candidate_location="Jakarta, Indonesia",
        job_text="Python required",
        description_hash="h1",
        router=router,
        semantic=semantic,
    )
    second = await run_match(
        connection,
        user_id="user-1",
        search_run_id="run-1",
        job_id="job-1",
        candidate_profile_id="prof-1",
        profile=CANDIDATE,
        candidate_location="Jakarta, Indonesia",
        job_text="Python required",
        description_hash="h1",
        router=router,
        semantic=semantic,
    )

    upserts = [
        params
        for query, params in connection.executed
        if "insert into public.job_matches" in query.lower() and "on conflict" in query.lower()
    ]
    assert len(upserts) == 2
    assert upserts[0] == upserts[1]
    assert first.overall_score == second.overall_score


@pytest.mark.asyncio
async def test_critical_language_gap_forces_not_recommended() -> None:
    requirements = [
        JobRequirement(category="skill", value="Python", criticality="must", evidence="Python required"),
        JobRequirement(category="language", value="Japanese", criticality="must", evidence="Japanese required"),
    ]
    connection = _Connection(
        requirements_row={"description_hash": "h1", "requirements": {"requirements": [r.model_dump(mode="json") for r in requirements]}}
    )
    router = _FakeRouter(_explanation_data())

    result = await run_match(
        connection,
        user_id="user-1",
        search_run_id="run-1",
        job_id="job-1",
        candidate_profile_id="prof-1",
        profile=CANDIDATE,
        candidate_location=None,
        job_text="Japanese required",
        description_hash="h1",
        router=router,
        semantic=SemanticMatcher(client=None),
    )

    assert result.verdict == "not_recommended"
    assert [gap.value for gap in result.critical_gaps] == ["Japanese"]
    assert result.overall_score >= 70


@pytest.mark.asyncio
async def test_match_run_is_deterministic_across_providers() -> None:
    connection = _Connection(
        requirements_row={
            "description_hash": "h1",
            "requirements": _requirements_json(),
        }
    )
    semantic = SemanticMatcher(client=None)

    result_a = await run_match(
        connection,
        user_id="user-1",
        search_run_id="run-1",
        job_id="job-1",
        candidate_profile_id="prof-1",
        profile=CANDIDATE,
        candidate_location="Jakarta, Indonesia",
        job_text="Python required",
        description_hash="h1",
        router=_FakeRouter(_explanation_data()),
        semantic=semantic,
    )
    result_b = await run_match(
        connection,
        user_id="user-1",
        search_run_id="run-1",
        job_id="job-1",
        candidate_profile_id="prof-1",
        profile=CANDIDATE,
        candidate_location="Jakarta, Indonesia",
        job_text="Python required",
        description_hash="h1",
        router=_FakeRouter({"explanation": "other provider", "recommendations": ["Another grounded tip"]}),
        semantic=semantic,
    )

    assert result_a.overall_score == result_b.overall_score
    assert result_a.dimension_scores == result_b.dimension_scores
    assert result_a.verdict == result_b.verdict