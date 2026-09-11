"""Shared eligibility rules for current, specific job postings."""

import urllib.parse
from datetime import UTC, datetime, timedelta

from jobmatch_worker.jobs.models import DiscoveredJob

MAX_JOB_AGE_DAYS = 30

_NON_JOB_PATH_MARKERS = (
    "/articles/",
    "/blog/",
    "/career-advice/",
    "/career-guide/",
    "/job-search",
    "/jobs/search",
    "/resources/",
    "/salaries/",
    "/salary/",
)


def is_recent_job(job: DiscoveredJob, *, now: datetime | None = None) -> bool:
    """Return whether a job was published within the inclusive 30-day window."""
    published = job.published_at
    current = now or datetime.now(UTC)
    if published is None or published.tzinfo is None or current.tzinfo is None:
        return False
    published_utc = published.astimezone(UTC)
    current_utc = current.astimezone(UTC)
    return (
        published_utc <= current_utc
        and published_utc.date()
        >= current_utc.date() - timedelta(days=MAX_JOB_AGE_DAYS)
    )


def is_specific_job_url(url: str) -> bool:
    """Reject known content, advice, salary, and search result URLs."""
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    path = urllib.parse.unquote(parsed.path or "/").casefold()
    normalized_path = f"{path.rstrip('/')}/"
    return not any(marker in normalized_path for marker in _NON_JOB_PATH_MARKERS)


__all__ = ["MAX_JOB_AGE_DAYS", "is_recent_job", "is_specific_job_url"]
