"""Discovery preference predicate.

This module is intentionally pure: it only inspects a normalized job and the
selected search-profile preferences. It performs no I/O and never mutates the
job or the shared catalog.
"""

from __future__ import annotations

from collections.abc import Sequence

from jobmatch_worker.jobs.normalize import NormalizedJob, normalize_text


def _normalized_phrase(value: str) -> str:
    return normalize_text(value)


def matches_preferences(
    job: NormalizedJob,
    *,
    work_modes: Sequence[str],
    employment_types: Sequence[str],
    excluded_keywords: Sequence[str],
) -> bool:
    """Return whether a normalized job satisfies the discovery preferences.

    Empty preference sequences impose no restriction. Known work-mode and
    employment-type values outside the selected sets are rejected. Unknown
    (missing) metadata remains eligible so incomplete sources do not silently
    lose valid jobs; the dashboard exposes a stricter explicit result filter.

    Excluded keywords are trimmed, case-folded, and whitespace-collapsed, then
    matched as literal substrings in title, company, or description. Any match
    rejects the job. This is intentionally not whole-word or regex matching.
    """
    selected_modes = {mode for mode in work_modes if mode}
    if selected_modes and job.work_mode is not None and job.work_mode not in selected_modes:
        return False

    selected_types = {employment_type for employment_type in employment_types if employment_type}
    if (
        selected_types
        and job.employment_type is not None
        and job.employment_type not in selected_types
    ):
        return False

    excluded = [_normalized_phrase(value) for value in excluded_keywords if value.strip()]
    excluded = [phrase for phrase in excluded if phrase]
    if not excluded:
        return True

    haystacks = (
        _normalized_phrase(job.title),
        _normalized_phrase(job.company),
        _normalized_phrase(job.description),
    )
    return not any(phrase in haystack for phrase in excluded for haystack in haystacks)


__all__ = ["matches_preferences"]
