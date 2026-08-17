"""Deduplication and catalog persistence for discovered jobs.

A job's identity is its deterministic fingerprint over the normalized
company, title, location, and canonical URL. A secondary fuzzy check
catches near-duplicates from different sources: same normalized company
and location with a token-set ratio >= 95 on the title when the canonical
URLs differ. Deduplication always runs before any AI requirement
extraction is enqueued.
"""

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

from jobmatch_worker.jobs.normalize import NormalizedJob, normalize_text

_FUZZY_RATIO_THRESHOLD = 95
_UNKNOWN_IDENTITY_VALUES = frozenset({"", "-", "n/a", "na", "none", "null", "unknown"})


def _reliable_identity(value: str | None) -> str | None:
    normalized = normalize_text(value) if value else ""
    return None if normalized in _UNKNOWN_IDENTITY_VALUES else normalized


def job_fingerprint(job: NormalizedJob) -> str:
    """Deterministic SHA-256 over normalized identity fields."""
    identity = "\n".join(
        [
            normalize_text(job.company),
            normalize_text(job.title),
            normalize_text(job.location) if job.location else "",
            job.canonical_url,
        ]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def is_fuzzy_duplicate(left: NormalizedJob, right: NormalizedJob) -> bool:
    """True when two jobs with different URLs are near-duplicates.

    The fuzzy check applies only when both the normalized company and the
    normalized location match and the canonical URLs differ. The title
    similarity must reach ``_FUZZY_RATIO_THRESHOLD``.
    """
    if left.canonical_url == right.canonical_url:
        return False
    left_company = _reliable_identity(left.company)
    right_company = _reliable_identity(right.company)
    if left_company is None or right_company is None or left_company != right_company:
        return False
    left_location = _reliable_identity(left.location)
    right_location = _reliable_identity(right.location)
    if left_location is None or right_location is None or left_location != right_location:
        return False
    ratio = fuzz.token_set_ratio(
        normalize_text(left.title), normalize_text(right.title)
    )
    return ratio >= _FUZZY_RATIO_THRESHOLD


def dedupe_jobs(
    jobs: Sequence[NormalizedJob],
) -> tuple[list[NormalizedJob], int]:
    """Drop duplicates, returning (kept jobs, duplicate count).

    Exact duplicates (same fingerprint) are collapsed first, then a
    fuzzy secondary pass removes near-duplicates. First-seen order is
    preserved.
    """
    kept: list[NormalizedJob] = []
    fingerprints: set[str] = set()
    for job in jobs:
        fp = job_fingerprint(job)
        if fp in fingerprints:
            continue
        fingerprints.add(fp)
        kept.append(job)

    survivors: list[NormalizedJob] = []
    for job in kept:
        if any(is_fuzzy_duplicate(candidate, job) for candidate in survivors):
            continue
        survivors.append(job)

    return survivors, len(jobs) - len(survivors)


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """Outcome of persisting a deduplicated batch into the catalog."""

    inserted: int
    duplicates: int
    job_ids: tuple[str, ...] = ()


async def upsert_jobs(
    conn: Any,
    *,
    search_run_id: str,
    jobs: Sequence[NormalizedJob],
) -> UpsertResult:
    """Upsert jobs into the catalog and link them to the search run.

    New fingerprints are inserted; existing rows are refreshed
    (``last_seen_at``/``last_checked_at``) and counted as duplicates.
    Links into ``job_search_run_jobs`` are added idempotently. Runs on
    the connection passed by the caller inside its transaction.
    """
    kept, _ = dedupe_jobs(jobs)
    inserted = 0
    duplicates = 0
    job_ids: list[str] = []
    for job in kept:
        cursor = await conn.execute(
            """
            insert into public.jobs
              (fingerprint, title, company, location, country, region,
               work_mode, employment_type, salary_min, salary_max,
               salary_currency, description, source_name, original_url,
               canonical_url, published_at, first_seen_at, last_seen_at,
               last_checked_at)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now(), now())
            on conflict (fingerprint) do update
              set last_seen_at = now(), last_checked_at = now(),
                  status = 'active'
            returning id, (xmax = 0) as inserted
            """,
            (
                job_fingerprint(job),
                job.title,
                job.company,
                job.location,
                job.country,
                job.region,
                job.work_mode,
                job.employment_type,
                job.salary_min,
                job.salary_max,
                job.salary_currency,
                job.description,
                job.source_name,
                job.original_url,
                job.canonical_url,
                job.published_at,
            ),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RuntimeError("job upsert did not return a job id")
        job_ids.append(str(row["id"]))
        if row["inserted"]:
            inserted += 1
        else:
            duplicates += 1
        await conn.execute(
            """
            insert into public.job_search_run_jobs (search_run_id, job_id)
            values (%s, %s)
            on conflict do nothing
            """,
            (search_run_id, row["id"]),
        )
    return UpsertResult(
        inserted=inserted,
        duplicates=duplicates,
        job_ids=tuple(job_ids),
    )


__all__ = [
    "UpsertResult",
    "dedupe_jobs",
    "is_fuzzy_duplicate",
    "job_fingerprint",
    "upsert_jobs",
]
