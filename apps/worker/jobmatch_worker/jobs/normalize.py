"""Normalization of discovered jobs before catalog persistence.

Normalization produces the canonical fields used by the fingerprint and
deduplication layers: case-folded, whitespace-collapsed company/title/
location and the canonical URL. The display fields (original title,
company, description, URL) are preserved verbatim for the user.
"""

import re
from dataclasses import dataclass
from datetime import datetime

from jobmatch_worker.jobs.canonicalize import canonicalize_url
from jobmatch_worker.jobs.models import DiscoveredJob, EmploymentType, WorkMode

_VALID_REGIONS = frozenset({"indonesia", "global", "unknown"})
_WS_RUN = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class NormalizedJob:
    """A discovered job with canonical identity and persistence fields."""

    title: str
    company: str
    location: str | None
    country: str | None
    region: str
    work_mode: WorkMode | None
    employment_type: EmploymentType | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    description: str
    source_name: str
    source_key: str
    original_url: str
    canonical_url: str
    published_at: datetime | None


def normalize_text(value: str) -> str:
    """Case-fold and collapse whitespace for identity comparisons."""
    return _WS_RUN.sub(" ", value.strip()).casefold()


def normalize_region(region: str | None) -> str:
    """Map a run region onto the jobs.region vocabulary."""
    if region is None:
        return "unknown"
    folded = region.strip().casefold()
    return folded if folded in _VALID_REGIONS else "unknown"


def normalize_job(job: DiscoveredJob, *, region: str | None = None) -> NormalizedJob:
    """Build the normalized form of a discovered job.

    The canonical URL is derived from ``original_url``; every other
    identity field is case-folded and whitespace-collapsed while the
    display values remain untouched.
    """
    return NormalizedJob(
        title=job.title,
        company=job.company,
        location=normalize_text(job.location) if job.location else None,
        country=job.country,
        region=normalize_region(region),
        work_mode=job.work_mode,
        employment_type=job.employment_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.currency,
        description=job.description,
        source_name=job.source_name,
        source_key=job.source_key,
        original_url=job.original_url,
        canonical_url=canonicalize_url(job.original_url, source_key=job.source_key),
        published_at=job.published_at,
    )


__all__ = [
    "NormalizedJob",
    "normalize_job",
    "normalize_region",
    "normalize_text",
]