"""Bounded search-query generation for job discovery.

Queries are modeled as ``SearchQuery`` objects that separate the positive
search ``terms`` from ``negative_terms`` (excluded keywords). Connectors
decide how to encode the negative terms for their provider: some support
``-keyword`` or ``NOT`` syntax, others only quoted exclusions; the builder
never assumes provider-specific syntax.
"""

from collections.abc import Iterable
from typing import Self


class SearchQuery(str):
    """A single search query with optional negative terms.

    The query text is the string itself. ``negative_terms`` holds excluded
    keywords that a provider may support as negative/exclusion terms (for
    example ``-senior`` or ``NOT "senior"``); providers that cannot express
    exclusions should ignore them rather than bake them into the query text.
    """

    negative_terms: tuple[str, ...]

    def __new__(cls, terms: str, negative_terms: tuple[str, ...] = ()) -> Self:
        obj = super().__new__(cls, terms)
        obj.negative_terms = negative_terms
        return obj

    @property
    def terms(self) -> str:
        return str(self)


_MAX_ROLES = 3
_MAX_LOCATIONS = 2
_VALID_REGIONS = ("indonesia", "global")


def _clean(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        key = stripped.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(stripped)
    return cleaned


def build_queries(
    region: str,
    roles: list[str],
    locations: list[str],
    remote: bool = False,
    excluded_keywords: list[str] | None = None,
) -> list[SearchQuery]:
    """Build at most 6 search queries for a discovery run.

    Args:
        region: ``"indonesia"`` or ``"global"`` (case-insensitive).
            Indonesia mode appends the country name to every query.
        roles: Target roles. Blanks are filtered and duplicates removed
            case-insensitively (first-seen casing is kept). Must leave at
            least one role or ValueError is raised.
        locations: Preferred locations. Blanks are filtered; at most the
            first 2 distinct locations are used.
        remote: When true, appends "remote" to a query unless the query
            already contains it.
        excluded_keywords: Keywords the user wants to exclude. Stored on
            ``SearchQuery.negative_terms`` so each connector decides how
            (or whether) to express them for its provider.

    Returns:
        Up to 6 ``SearchQuery`` objects: top 3 roles each combined with
        at most 2 location variants (a role with no locations produces a
        role-only query).

    Raises:
        ValueError: If the region is unsupported or no role remains after
            blank filtering.
    """
    normalized_region = region.strip().casefold()
    if normalized_region not in _VALID_REGIONS:
        raise ValueError(f"unsupported region: {region!r}")

    clean_roles = _clean(roles)
    if not clean_roles:
        raise ValueError("at least one non-empty target role is required")

    clean_locations = _clean(locations)[:_MAX_LOCATIONS]
    clean_exclusions = tuple(_clean(excluded_keywords or []))

    queries: list[SearchQuery] = []
    for role in clean_roles[:_MAX_ROLES]:
        location_variants: Iterable[str | None] = clean_locations or [None]
        for location in location_variants:
            parts = [role]
            if location:
                parts.append(location)
            if normalized_region == "indonesia":
                parts.append("Indonesia")
            if remote and "remote" not in " ".join(parts).casefold():
                parts.append("remote")
            queries.append(SearchQuery(terms=" ".join(parts), negative_terms=clean_exclusions))
    return queries


__all__ = ["SearchQuery", "build_queries"]