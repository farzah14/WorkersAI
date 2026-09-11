from datetime import UTC, datetime, timedelta

from jobmatch_worker.jobs.indonesia import (
    is_indonesia_eligible,
    is_trusted_job_url,
    parse_extra_trusted_domains,
    rank_indonesia_jobs,
)
from jobmatch_worker.jobs.models import DiscoveredJob


def _job(
    *,
    title: str = "Data Engineer",
    location: str | None = "Jakarta",
    country: str | None = None,
    description: str = "Build data systems for our Jakarta team.",
    url: str = "https://glints.com/id/opportunities/jobs/data-engineer/123",
    work_mode: str | None = "hybrid",
    published_at: datetime | None = None,
) -> DiscoveredJob:
    return DiscoveredJob(
        source_name="Tavily",
        source_key="tavily",
        title=title,
        company="Acme",
        location=location,
        country=country,
        description=description,
        original_url=url,
        work_mode=work_mode,
        published_at=published_at,
    )


def test_trusted_urls_accept_reviewed_boards_and_ats() -> None:
    assert is_trusted_job_url("https://www.jobstreet.co.id/id/job/123")
    assert is_trusted_job_url("https://glints.com/id/opportunities/jobs/engineer/123")
    assert is_trusted_job_url("https://jobs.lever.co/acme/123")
    assert is_trusted_job_url("https://boards.greenhouse.io/acme/jobs/123")


def test_trusted_urls_reject_unknown_lookalike_and_content_hosts() -> None:
    assert not is_trusted_job_url("https://careers.unknown.example/jobs/123")
    assert not is_trusted_job_url("https://jobstreet.co.id.evil.example/jobs/123")
    assert not is_trusted_job_url("https://example.blogspot.com/jobs/123")


def test_operator_domains_are_normalized_but_cannot_override_blocked_hosts() -> None:
    domains = parse_extra_trusted_domains(
        " Careers.Acme.co.id,https://jobs.example.org/path, careers.acme.co.id "
    )

    assert domains == frozenset({"careers.acme.co.id", "jobs.example.org"})
    assert is_trusted_job_url("https://id.careers.acme.co.id/jobs/42", domains)
    assert not is_trusted_job_url("https://example.blogspot.com/jobs/42", {"blogspot.com"})


def test_indonesia_eligibility_accepts_explicit_country_location_or_remote_scope() -> None:
    assert is_indonesia_eligible(_job(country="Indonesia", location=None))
    assert is_indonesia_eligible(_job(location="Bandung"))
    assert is_indonesia_eligible(
        _job(location=None, work_mode="remote", description="Remote within Indonesia. Build APIs.")
    )
    assert is_indonesia_eligible(
        _job(location=None, description="Location: Surabaya, Indonesia. Build APIs.")
    )


def test_indonesia_eligibility_rejects_missing_foreign_and_worldwide_remote_evidence() -> None:
    assert not is_indonesia_eligible(_job(location=None, country=None, description="Build APIs."))
    assert not is_indonesia_eligible(
        _job(location="Singapore", country="Singapore", description="Support Indonesia customers.")
    )
    assert not is_indonesia_eligible(
        _job(location="Remote - Worldwide", work_mode="remote", description="Work from anywhere.")
    )


def test_rank_indonesia_jobs_prefers_role_location_mode_and_freshness() -> None:
    now = datetime.now(UTC)
    exact = _job(title="Senior Data Engineer", location="Jakarta", published_at=now)
    wrong_role = _job(title="Marketing Manager", location="Jakarta", published_at=now)
    wrong_location = _job(title="Data Engineer", location="Surabaya", published_at=now)
    old = _job(title="Data Engineer", location="Jakarta", published_at=now - timedelta(days=90))

    ranked = rank_indonesia_jobs(
        [wrong_role, wrong_location, old, exact],
        roles=["Data Engineer"],
        locations=["Jakarta"],
        work_modes=["hybrid"],
    )

    assert ranked == [exact, old, wrong_location, wrong_role]


def test_rank_indonesia_jobs_keeps_input_order_for_exact_ties() -> None:
    first = _job(title="Backend Engineer", url="https://glints.com/id/jobs/first")
    second = _job(title="Backend Engineer", url="https://glints.com/id/jobs/second")

    assert rank_indonesia_jobs(
        [first, second], roles=["Engineer"], locations=[], work_modes=[]
    ) == [first, second]
