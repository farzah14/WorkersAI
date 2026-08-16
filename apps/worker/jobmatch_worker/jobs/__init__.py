"""Job discovery contracts: normalized jobs and query building."""

from jobmatch_worker.jobs.canonicalize import canonicalize_url
from jobmatch_worker.jobs.dedupe import (
    UpsertResult,
    dedupe_jobs,
    is_fuzzy_duplicate,
    job_fingerprint,
    upsert_jobs,
)
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.normalize import NormalizedJob, normalize_job
from jobmatch_worker.jobs.query import SearchQuery, build_queries

__all__ = [
    "DiscoveredJob",
    "DiscoveryCandidateUrl",
    "NormalizedJob",
    "SearchQuery",
    "UpsertResult",
    "build_queries",
    "canonicalize_url",
    "dedupe_jobs",
    "is_fuzzy_duplicate",
    "job_fingerprint",
    "normalize_job",
    "upsert_jobs",
]