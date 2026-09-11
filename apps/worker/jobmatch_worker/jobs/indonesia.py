"""Strict, deterministic policy for Indonesia job discovery."""

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
import re
import urllib.parse

from jobmatch_worker.jobs.models import DiscoveredJob


DEFAULT_TRUSTED_DOMAINS = frozenset(
    {
        "jobstreet.co.id",
        "jobstreet.com",
        "glints.com",
        "kalibrr.com",
        "dealls.com",
        "kitalulus.com",
        "greenhouse.io",
        "lever.co",
        "workable.com",
        "ashbyhq.com",
        "smartrecruiters.com",
    }
)
_BLOCKED_DOMAINS = frozenset(
    {
        "blogspot.com",
        "medium.com",
        "wordpress.com",
        "tumblr.com",
    }
)
_INDONESIA_TERMS = (
    "indonesia",
    "jakarta",
    "bandung",
    "surabaya",
    "medan",
    "semarang",
    "makassar",
    "yogyakarta",
    "jogja",
    "denpasar",
    "bali",
    "bekasi",
    "depok",
    "tangerang",
    "bogor",
    "batam",
    "palembang",
    "pekanbaru",
    "pontianak",
    "balikpapan",
    "samarinda",
    "banjarmasin",
    "manado",
    "padang",
    "malang",
    "solo",
    "surakarta",
    "aceh",
    "sumatra",
    "jawa",
    "kalimantan",
    "sulawesi",
    "papua",
    "maluku",
    "nusa tenggara",
)
_LOCATION_PREFIXES = (
    "location",
    "lokasi",
    "based in",
    "berlokasi di",
    "remote within",
    "remote in",
    "remote from",
    "work from",
    "work anywhere in",
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _domain_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def parse_extra_trusted_domains(value: str) -> frozenset[str]:
    domains: set[str] = set()
    for entry in value.split(","):
        candidate = entry.strip()
        if not candidate:
            continue
        parsed = urllib.parse.urlsplit(
            candidate if "://" in candidate else f"https://{candidate}"
        )
        host = (parsed.hostname or "").rstrip(".").casefold()
        if host and re.fullmatch(r"[a-z0-9.-]+", host):
            domains.add(host)
    return frozenset(domains)


def is_trusted_job_url(
    url: str, extra_domains: Iterable[str] = ()
) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").rstrip(".").casefold()
    if parsed.scheme != "https" or not host:
        return False
    if any(_domain_matches(host, domain) for domain in _BLOCKED_DOMAINS):
        return False
    trusted = DEFAULT_TRUSTED_DOMAINS | {
        domain.rstrip(".").casefold() for domain in extra_domains if domain
    }
    return any(_domain_matches(host, domain) for domain in trusted)


def _contains_indonesia_term(value: str | None) -> bool:
    folded = (value or "").casefold()
    return any(
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", folded)
        for term in _INDONESIA_TERMS
    )


def is_indonesia_eligible(job: DiscoveredJob) -> bool:
    country = (job.country or "").strip().casefold()
    if country:
        return country in {"id", "idn", "indonesia", "republic of indonesia"}
    if _contains_indonesia_term(job.location):
        return True

    description = job.description.casefold()
    for prefix in _LOCATION_PREFIXES:
        for match in re.finditer(re.escape(prefix), description):
            evidence = description[match.start() : match.end() + 80]
            if _contains_indonesia_term(evidence):
                return True
    return False


def _tokens(value: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(value.casefold()))


def _relevance_score(
    job: DiscoveredJob,
    *,
    roles: Sequence[str],
    locations: Sequence[str],
    work_modes: Sequence[str],
) -> float:
    title_tokens = _tokens(job.title)
    role_score = 0.0
    for role in roles:
        role_tokens = _tokens(role)
        if role_tokens:
            role_score = max(
                role_score,
                60.0 * len(title_tokens & role_tokens) / len(role_tokens),
            )

    location = (job.location or "").casefold()
    location_score = 25.0 if any(
        requested.strip().casefold() in location
        for requested in locations
        if requested.strip()
    ) else 0.0
    requested_modes = {mode.strip().casefold() for mode in work_modes}
    mode_score = 15.0 if job.work_mode in requested_modes else 0.0

    freshness_score = 0.0
    if job.published_at is not None:
        published = job.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=UTC)
        age_days = max(0, (datetime.now(UTC) - published).days)
        freshness_score = 10.0 if age_days <= 30 else 5.0 if age_days <= 90 else 0.0
    return role_score + location_score + mode_score + freshness_score


def rank_indonesia_jobs(
    jobs: Sequence[DiscoveredJob],
    *,
    roles: Sequence[str],
    locations: Sequence[str],
    work_modes: Sequence[str],
) -> list[DiscoveredJob]:
    return sorted(
        jobs,
        key=lambda job: _relevance_score(
            job,
            roles=roles,
            locations=locations,
            work_modes=work_modes,
        ),
        reverse=True,
    )


__all__ = [
    "DEFAULT_TRUSTED_DOMAINS",
    "is_indonesia_eligible",
    "is_trusted_job_url",
    "parse_extra_trusted_domains",
    "rank_indonesia_jobs",
]
