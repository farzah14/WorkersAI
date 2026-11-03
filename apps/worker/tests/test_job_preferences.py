from __future__ import annotations

import pytest

from jobmatch_worker.jobs.normalize import NormalizedJob
from jobmatch_worker.jobs.preferences import matches_preferences


def job(
    *,
    title: str = "Data Engineer",
    company: str = "Acme",
    description: str = "Build reliable data pipelines.",
    work_mode: str | None = "remote",
    employment_type: str | None = "full-time",
) -> NormalizedJob:
    return NormalizedJob(
        title=title,
        company=company,
        location=None,
        country=None,
        region="global",
        work_mode=work_mode,  # type: ignore[arg-type]
        employment_type=employment_type,  # type: ignore[arg-type]
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        description=description,
        source_name="test",
        source_key="test",
        original_url="https://example.test/jobs/1",
        canonical_url="https://example.test/jobs/1",
        published_at=None,
    )


@pytest.mark.parametrize(
    ("preferences", "candidate", "expected"),
    [
        # P1: known work mode outside the selected set is rejected.
        ({"work_modes": ["remote"]}, job(work_mode="on-site"), False),
        # P2: unknown work mode stays eligible during discovery.
        ({"work_modes": ["remote"]}, job(work_mode=None), True),
        ({"work_modes": ["remote"]}, job(work_mode="remote"), True),
        ({"work_modes": []}, job(work_mode="on-site"), True),
        # P3: known employment type outside the selected set is rejected.
        ({"employment_types": ["full-time"]}, job(employment_type="internship"), False),
        # P4: empty employment preference imposes no restriction.
        ({"employment_types": []}, job(employment_type="internship"), True),
        ({"employment_types": ["full-time"]}, job(employment_type=None), True),
        (
            {"employment_types": ["full-time"], "work_modes": ["remote"]},
            job(employment_type="contract", work_mode="remote"),
            False,
        ),
        (
            {"employment_types": ["full-time"], "work_modes": ["remote"]},
            job(employment_type="full-time", work_mode="hybrid"),
            False,
        ),
    ],
)
def test_selected_preferences_accept_only_compatible_known_values(
    preferences: dict[str, list[str]],
    candidate: NormalizedJob,
    expected: bool,
) -> None:
    assert (
        matches_preferences(
            candidate,
            work_modes=preferences.get("work_modes", []),
            employment_types=preferences.get("employment_types", []),
            excluded_keywords=[],
        )
        is expected
    )


@pytest.mark.parametrize(
    ("excluded", "candidate", "expected"),
    [
        # P5: casefold and whitespace collapse before literal substring matching.
        (
            ["senior engineer"],
            job(description="SENIOR   ENGINEER required"),
            False,
        ),
        # P6: punctuation is literal, not a regular expression.
        (["C++"], job(title="C++ Developer"), False),
        # P7: documented substring semantics; java matches JavaScript.
        (["java"], job(title="JavaScript Developer"), False),
        (["staff engineer"], job(title="Senior Engineering Manager"), True),
        # Substring semantics intentionally match inside longer words.
        (["senior engineer"], job(title="Senior Engineering Manager"), False),
        (["  "], job(), True),
        (["", "   "], job(), True),
        (["sales"], job(title="Sales Engineer"), False),
        (["acme"], job(company="ACME Labs"), False),
        (["kubernetes"], job(description="Kubernetes and Terraform"), False),
        (["kubernetes"], job(description="Docker and Terraform"), True),
    ],
)
def test_exclusions_match_normalized_literal_substrings(
    excluded: list[str],
    candidate: NormalizedJob,
    expected: bool,
) -> None:
    assert (
        matches_preferences(
            candidate,
            work_modes=[],
            employment_types=[],
            excluded_keywords=excluded,
        )
        is expected
    )


def test_any_exclusion_rejects_even_when_other_fields_match() -> None:
    candidate = job(
        title="Backend Engineer",
        company="Acme",
        description="Python services",
    )

    assert not matches_preferences(
        candidate,
        work_modes=["remote"],
        employment_types=["full-time"],
        excluded_keywords=["acme"],
    )
