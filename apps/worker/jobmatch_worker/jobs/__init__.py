"""Job discovery contracts: normalized jobs and query building."""

from jobmatch_worker.jobs.models import DiscoveredJob
from jobmatch_worker.jobs.query import SearchQuery, build_queries

__all__ = ["DiscoveredJob", "SearchQuery", "build_queries"]