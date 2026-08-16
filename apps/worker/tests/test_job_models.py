from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl


def test_discovered_job_accepts_complete_payload() -> None:
    job = DiscoveredJob.model_validate(
        {
            "source_name": "Greenhouse",
            "source_key": "gh-1234",
            "title": "Data Engineer",
            "company": "Acme Corp",
            "location": "Jakarta",
            "country": "Indonesia",
            "work_mode": "hybrid",
            "employment_type": "full-time",
            "salary_min": 15000000,
            "salary_max": 25000000,
            "currency": "IDR",
            "description": "Build data pipelines.",
            "original_url": "https://boards.greenhouse.io/acme/jobs/1234",
            "published_at": datetime(2026, 8, 1, tzinfo=UTC),
        }
    )
    assert job.title == "Data Engineer"
    assert job.source_key == "gh-1234"
    assert job.salary_min == 15000000
    assert job.published_at is not None


def test_discovered_job_defaults_optionals() -> None:
    job = DiscoveredJob(
        source_name="Lever",
        source_key="lv-1",
        title="Data Analyst",
        company="Beta",
        description="Analyze data.",
        original_url="https://jobs.lever.co/beta/1",
    )
    assert job.location is None
    assert job.country is None
    assert job.work_mode is None
    assert job.employment_type is None
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.currency is None
    assert job.published_at is None


def test_discovered_job_strips_whitespace() -> None:
    job = DiscoveredJob.model_validate(
        {
            "source_name": "Greenhouse",
            "source_key": "gh-2",
            "title": "  Data Engineer  ",
            "company": "  Acme  ",
            "description": "  Build pipelines.  ",
            "original_url": "  https://boards.greenhouse.io/acme/jobs/2  ",
        }
    )
    assert job.title == "Data Engineer"
    assert job.company == "Acme"
    assert job.description == "Build pipelines."
    assert job.original_url == "https://boards.greenhouse.io/acme/jobs/2"


@pytest.mark.parametrize("field", ["title", "company", "description", "original_url"])
def test_discovered_job_requires_non_empty_fields(field: str) -> None:
    payload = {
        "source_name": "Greenhouse",
        "source_key": "gh-3",
        "title": "Data Engineer",
        "company": "Acme",
        "description": "Build pipelines.",
        "original_url": "https://boards.greenhouse.io/acme/jobs/3",
    }
    payload[field] = "   "
    with pytest.raises(ValidationError):
        DiscoveredJob.model_validate(payload)


def test_discovered_job_rejects_negative_salary() -> None:
    with pytest.raises(ValidationError):
        DiscoveredJob(
            source_name="Lever",
            source_key="lv-2",
            title="Data Analyst",
            company="Beta",
            description="Analyze data.",
            original_url="https://jobs.lever.co/beta/2",
            salary_min=-1,
        )


def test_discovered_job_rejects_salary_min_above_max() -> None:
    with pytest.raises(ValidationError):
        DiscoveredJob(
            source_name="Lever",
            source_key="lv-3",
            title="Data Analyst",
            company="Beta",
            description="Analyze data.",
            original_url="https://jobs.lever.co/beta/3",
            salary_min=30000000,
            salary_max=15000000,
        )


def test_discovered_job_accepts_equal_salary_bounds() -> None:
    job = DiscoveredJob(
        source_name="Lever",
        source_key="lv-4",
        title="Data Analyst",
        company="Beta",
        description="Analyze data.",
        original_url="https://jobs.lever.co/beta/4",
        salary_min=15000000,
        salary_max=15000000,
    )
    assert job.salary_min == job.salary_max == 15000000


def test_discovered_job_rejects_oversized_or_control_character_url() -> None:
    base = {
        "source_name": "Lever",
        "source_key": "lv-4b",
        "title": "Data Analyst",
        "company": "Beta",
        "description": "Analyze data.",
    }
    with pytest.raises(ValidationError):
        DiscoveredJob(**base, original_url="https://example.com/" + "x" * 2048)
    with pytest.raises(ValidationError):
        DiscoveredJob(**base, original_url="https://example.com/jobs/1\nnext")


def test_candidate_url_rejects_oversized_or_control_character_url() -> None:
    with pytest.raises(ValidationError):
        DiscoveryCandidateUrl(url="https://example.com/" + "x" * 2048)
    with pytest.raises(ValidationError):
        DiscoveryCandidateUrl(url="https://example.com/jobs/1\nnext")


@pytest.mark.parametrize(
    "work_mode",
    ["on-site", "hybrid", "remote"],
)
def test_discovered_job_accepts_db_work_modes(work_mode: str) -> None:
    job = DiscoveredJob(
        source_name="Lever",
        source_key="lv-5",
        title="Data Analyst",
        company="Beta",
        description="Analyze data.",
        original_url="https://jobs.lever.co/beta/5",
        work_mode=work_mode,
    )
    assert job.work_mode == work_mode


@pytest.mark.parametrize("work_mode", ["onsite", "unknown", "flexible"])
def test_discovered_job_rejects_non_db_work_modes(work_mode: str) -> None:
    with pytest.raises(ValidationError):
        DiscoveredJob(
            source_name="Lever",
            source_key="lv-6",
            title="Data Analyst",
            company="Beta",
            description="Analyze data.",
            original_url="https://jobs.lever.co/beta/6",
            work_mode=work_mode,
        )
