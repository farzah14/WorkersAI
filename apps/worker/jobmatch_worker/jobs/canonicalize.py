"""Canonical URL building for discovered jobs.

A canonical URL is the smallest stable identifier for a job posting:
HTTPS only, no credentials, lowercase host, no fragment, no tracking
parameters, sorted remaining query parameters, and a normalized trailing
slash. Two URLs that differ only in tracking noise resolve to the same
canonical URL, so the fingerprint layer can treat them as one job.
"""

import urllib.parse

from jobmatch_worker.jobs.connectors.base import SourceConfigError, SourceDataError

# Query parameters that carry tracking or referral context only and must
# never influence the canonical identity of a job.
TRACKING_QUERY_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "gh_src",
        "gh_srcid",
        "hsctatracking",
        "igshid",
        "mc_cid",
        "mc_eid",
        "spm",
        "cvid",
        "yclid",
        "_hsenc",
        "_hsmi",
    }
)
_TRACKING_PREFIXES = ("utm_",)


def canonicalize_url(url: str, *, source_key: str) -> str:
    """Return the canonical form of a job URL, or raise a source error.

    Raises ``SourceConfigError`` for non-HTTPS URLs or URLs with embedded
    credentials, and ``SourceDataError`` for URLs without a host or with
    unparseable components (malformed IPv6, invalid ports).
    """
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise SourceDataError(source_key, "malformed URL") from exc
    if parsed.scheme != "https":
        raise SourceConfigError(source_key, "only https URLs are allowed")
    if parsed.username or parsed.password:
        raise SourceConfigError(source_key, "URL must not embed credentials")
    if not parsed.netloc or not parsed.hostname:
        raise SourceDataError(source_key, "URL has no host")

    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = f"{hostname}:{port}" if port else hostname

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    pairs: list[tuple[str, str]] = []
    for pair in parsed.query.split("&"):
        if not pair:
            continue
        key, separator, value = pair.partition("=")
        if key and not _is_tracking_key(key):
            pairs.append((key, value if separator else ""))
    query = "&".join(f"{key}={value}" for key, value in sorted(pairs))

    return urllib.parse.urlunsplit((parsed.scheme, netloc, path, query, ""))


def _is_tracking_key(key: str) -> bool:
    folded = key.casefold()
    return folded in TRACKING_QUERY_PARAMS or folded.startswith(_TRACKING_PREFIXES)


__all__ = ["TRACKING_QUERY_PARAMS", "canonicalize_url"]