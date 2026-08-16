"""Job discovery contracts: normalized jobs and query building."""

from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.query import SearchQuery, build_queries

__all__ = ["DiscoveredJob", "DiscoveryCandidateUrl", "SearchQuery", "build_queries"]