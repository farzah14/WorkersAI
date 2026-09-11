from datetime import UTC, datetime

import pytest

from jobmatch_worker.jobs.models import DiscoveredJob
from jobmatch_worker.jobs.validity import is_recent_job, is_specific_job_url

NOW = datetime(2026, 9, 11, 17, 0, tzinfo=UTC)


def _job(published_at: datetime | None) -> DiscoveredJob:
    return DiscoveredJob(
        source_name="Test",
        source_key="test",
        title="Data Engineer",
        company="Acme",
        description="Build data systems.",
        original_url="https://example.com/jobs/data-engineer-123",
        published_at=published_at,
    )


def test_recent_job_accepts_today_and_exactly_thirty_calendar_days() -> None:
    assert is_recent_job(_job(datetime(2026, 9, 11, 16, 59, tzinfo=UTC)), now=NOW)
    assert is_recent_job(_job(datetime(2026, 8, 12, 0, 0, tzinfo=UTC)), now=NOW)


@pytest.mark.parametrize(
    "published_at",
    [
        None,
        datetime(2026, 8, 11, 23, 59, tzinfo=UTC),
        datetime(2026, 9, 11, 17, 1, tzinfo=UTC),
        datetime(2026, 9, 10, 12, 0, tzinfo=UTC).replace(tzinfo=None),
    ],
)
def test_recent_job_rejects_missing_old_future_and_naive_dates(
    published_at: datetime | None,
) -> None:
    assert not is_recent_job(_job(published_at), now=NOW)


def test_specific_job_url_rejects_content_and_search_pages() -> None:
    assert not is_specific_job_url(
        "https://id.jobstreet.com/career-advice/role/data-engineer/salary"
    )
    assert not is_specific_job_url("https://example.com/jobs/search?q=data")
    assert not is_specific_job_url("https://example.com/blog/data-careers")
    assert is_specific_job_url("https://example.com/jobs/data-engineer-123")
