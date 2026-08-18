"""Tests for job normalization, canonicalization, and deduplication.

Covers the pure pipeline that runs before any AI requirement extraction:
canonical URL building, deterministic fingerprints, fuzzy duplicate
detection, and the catalog upsert.
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from jobmatch_worker.jobs.canonicalize import canonicalize_url
from jobmatch_worker.jobs.connectors.base import SourceConfigError, SourceDataError
from jobmatch_worker.jobs.dedupe import (
    dedupe_jobs,
    is_fuzzy_duplicate,
    job_fingerprint,
    upsert_jobs,
)
from jobmatch_worker.jobs.models import DiscoveredJob
from jobmatch_worker.jobs.normalize import normalize_job


def make_job(**overrides: Any) -> DiscoveredJob:
    base: dict[str, Any] = {
        "source_name": "Greenhouse",
        "source_key": "greenhouse:acme",
        "title": "Data Engineer",
        "company": "Acme Corp",
        "location": "Jakarta",
        "country": "Indonesia",
        "description": "Build data pipelines.",
        "original_url": "https://boards.greenhouse.io/acme/jobs/123",
    }
    base.update(overrides)
    return DiscoveredJob(**base)


def make_normalized(**overrides: Any) -> Any:
    job = make_job(**{k: v for k, v in overrides.items() if k != "region"})
    return normalize_job(job, region=overrides.get("region"))


class TestCanonicalizeUrl:
    def test_strips_utm_params_and_preserves_semantic_params(self) -> None:
        url = (
            "https://Careers.Acme.com/jobs/42?"
            "utm_source=linkedin&utm_campaign=launch&job_id=42&keyword=data"
        )
        assert canonicalize_url(url, source_key="test") == (
            "https://careers.acme.com/jobs/42?job_id=42&keyword=data"
        )

    def test_strips_gh_src_and_common_referral_params(self) -> None:
        url = (
            "https://careers.acme.com/jobs/42?"
            "gh_src=abc123&gh_srcid=xyz&fbclid=fb1&gclid=gc1&id=42"
        )
        assert canonicalize_url(url, source_key="test") == (
            "https://careers.acme.com/jobs/42?id=42"
        )

    def test_sorts_retained_query_params(self) -> None:
        url = "https://careers.acme.com/jobs/42?z=1&a=2&m=3"
        assert canonicalize_url(url, source_key="test") == (
            "https://careers.acme.com/jobs/42?a=2&m=3&z=1"
        )

    def test_lowercases_hostname_and_preserves_port(self) -> None:
        url = "https://Jobs.Acme.COM:8443/jobs/42"
        assert canonicalize_url(url, source_key="test") == (
            "https://jobs.acme.com:8443/jobs/42"
        )

    def test_removes_fragment(self) -> None:
        url = "https://careers.acme.com/jobs/42#section"
        assert canonicalize_url(url, source_key="test") == (
            "https://careers.acme.com/jobs/42"
        )

    def test_normalizes_trailing_slash(self) -> None:
        assert canonicalize_url("https://careers.acme.com/jobs/42/", source_key="test") == (
            "https://careers.acme.com/jobs/42"
        )
        assert canonicalize_url("https://careers.acme.com/", source_key="test") == (
            "https://careers.acme.com/"
        )

    def test_rejects_non_https_scheme(self) -> None:
        with pytest.raises(SourceConfigError):
            canonicalize_url("http://careers.acme.com/jobs/42", source_key="test")

    def test_rejects_embedded_credentials(self) -> None:
        with pytest.raises(SourceConfigError):
            canonicalize_url(
                "https://user:pass@careers.acme.com/jobs/42", source_key="test"
            )

    def test_rejects_url_without_host(self) -> None:
        with pytest.raises(SourceDataError):
            canonicalize_url("https:///jobs/42", source_key="test")

    def test_rejects_malformed_ipv6_url(self) -> None:
        with pytest.raises(SourceDataError):
            canonicalize_url("https://[::1/jobs/42", source_key="test")

    def test_rejects_invalid_port(self) -> None:
        with pytest.raises(SourceDataError):
            canonicalize_url("https://careers.acme.com:abc/jobs/42", source_key="test")
        with pytest.raises(SourceDataError):
            canonicalize_url("https://careers.acme.com:99999/jobs/42", source_key="test")

    def test_preserves_ipv6_brackets(self) -> None:
        assert canonicalize_url("https://[2606:4700::1111]:8080/jobs/42", source_key="test") == (
            "https://[2606:4700::1111]:8080/jobs/42"
        )

    def test_hostname_casefold_does_not_expand(self) -> None:
        assert canonicalize_url("https://Exaßmple.com/jobs/42", source_key="test") == (
            "https://exaßmple.com/jobs/42"
        )


class TestNormalizeJob:
    def test_canonicalizes_url_and_keeps_original(self) -> None:
        job = make_job(
            original_url="https://Careers.Acme.com/jobs/123?utm_source=x&id=1"
        )
        normalized = normalize_job(job, region="indonesia")
        assert normalized.original_url == "https://Careers.Acme.com/jobs/123?utm_source=x&id=1"
        assert normalized.canonical_url == "https://careers.acme.com/jobs/123?id=1"

    def test_maps_region(self) -> None:
        assert normalize_job(make_job(), region="indonesia").region == "indonesia"
        assert normalize_job(make_job(), region="global").region == "global"
        assert normalize_job(make_job(), region=None).region == "unknown"
        assert normalize_job(make_job(), region="INVALID").region == "unknown"

    def test_maps_currency_to_salary_currency(self) -> None:
        normalized = normalize_job(make_job(currency="IDR", salary_min=10_000_000.0))
        assert normalized.salary_currency == "IDR"
        assert normalized.salary_min == 10_000_000.0


class TestFingerprint:
    def test_same_company_title_location_canonical_url_match(self) -> None:
        a = make_normalized(
            company="  Acme   Corp ",
            title="Data Engineer",
            location="Jakarta",
            original_url="https://boards.greenhouse.io/acme/jobs/1",
        )
        b = make_normalized(
            company="acme corp",
            title="Data Engineer",
            location="jakarta",
            original_url="https://boards.greenhouse.io/acme/jobs/1?utm_source=x",
        )
        assert job_fingerprint(a) == job_fingerprint(b)

    def test_different_canonical_urls_differ(self) -> None:
        a = make_normalized(original_url="https://boards.greenhouse.io/acme/jobs/1")
        b = make_normalized(original_url="https://boards.greenhouse.io/acme/jobs/2")
        assert job_fingerprint(a) != job_fingerprint(b)

    def test_different_title_differ(self) -> None:
        a = make_normalized(title="Data Engineer")
        b = make_normalized(title="Data Analyst")
        assert job_fingerprint(a) != job_fingerprint(b)

    def test_missing_location_is_empty_string(self) -> None:
        a = make_normalized(location=None)
        b = make_normalized(location="")
        assert job_fingerprint(a) == job_fingerprint(b)


class TestFuzzyDuplicate:
    def test_high_similarity_title_same_company_location_matches(self) -> None:
        a = make_normalized(
            title="Senior Data Engineer",
            original_url="https://boards.greenhouse.io/acme/jobs/1",
        )
        b = make_normalized(
            title="Data Engineer (Senior)",
            original_url="https://boards.greenhouse.io/acme/jobs/2",
        )
        assert is_fuzzy_duplicate(a, b)

    def test_different_company_is_not_a_duplicate(self) -> None:
        a = make_normalized(company="Acme Corp", original_url="https://x.example/1")
        b = make_normalized(company="Globex", original_url="https://x.example/2")
        assert not is_fuzzy_duplicate(a, b)

    def test_different_location_is_not_a_duplicate(self) -> None:
        a = make_normalized(location="Jakarta", original_url="https://x.example/1")
        b = make_normalized(location="Bandung", original_url="https://x.example/2")
        assert not is_fuzzy_duplicate(a, b)

    def test_low_similarity_title_is_not_a_duplicate(self) -> None:
        a = make_normalized(title="Data Engineer", original_url="https://x.example/1")
        b = make_normalized(title="Receptionist", original_url="https://x.example/2")
        assert not is_fuzzy_duplicate(a, b)

    def test_same_canonical_url_is_not_fuzzy_compared(self) -> None:
        a = make_normalized(original_url="https://x.example/1")
        b = make_normalized(original_url="https://x.example/1")
        assert not is_fuzzy_duplicate(a, b)

    def test_unknown_identity_fields_do_not_fuzzy_match(self) -> None:
        a = make_normalized(
            company="Unknown",
            location=None,
            original_url="https://x.example/1",
        )
        b = make_normalized(
            company="Unknown",
            location=None,
            original_url="https://y.example/2",
        )
        assert not is_fuzzy_duplicate(a, b)


class TestDedupeJobs:
    def test_exact_duplicate_collapses_and_counts(self) -> None:
        jobs = [
            make_normalized(original_url="https://x.example/1"),
            make_normalized(original_url="https://x.example/1?utm_source=a"),
        ]
        kept, duplicates = dedupe_jobs(jobs)
        assert len(kept) == 1
        assert duplicates == 1

    def test_fuzzy_duplicate_collapses_and_counts(self) -> None:
        jobs = [
            make_normalized(title="Data Engineer", original_url="https://x.example/1"),
            make_normalized(
                title="Data Engineer (Remote)", original_url="https://x.example/2"
            ),
        ]
        kept, duplicates = dedupe_jobs(jobs)
        assert len(kept) == 1
        assert duplicates == 1

    def test_distinct_jobs_are_kept_in_order(self) -> None:
        jobs = [
            make_normalized(title="Data Engineer", original_url="https://x.example/1"),
            make_normalized(title="Data Analyst", original_url="https://x.example/2"),
            make_normalized(title="ML Engineer", original_url="https://x.example/3"),
        ]
        kept, duplicates = dedupe_jobs(jobs)
        assert [j.title for j in kept] == ["Data Engineer", "Data Analyst", "ML Engineer"]
        assert duplicates == 0


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self._index = 0

    async def fetchone(self) -> dict[str, Any] | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._rows_by_position: list[dict[str, Any]] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self._rows_by_position = rows

    async def execute(self, query: str, params: tuple[Any, ...]) -> FakeCursor:
        self.executed.append((query, params))
        if self._rows_by_position:
            return FakeCursor([self._rows_by_position.pop(0)])
        return FakeCursor([])


class TestUpsertJobs:
    def test_upsert_inserts_new_rows_and_links_run(self) -> None:
        conn = FakeConnection()
        conn.set_rows([{"id": "job-1", "inserted": True}])
        jobs = [make_normalized(original_url="https://x.example/1")]

        result = asyncio.run(upsert_jobs(conn, search_run_id="run-1", jobs=jobs))

        assert result.inserted == 1
        assert result.duplicates == 0
        insert_sql, insert_params = conn.executed[0]
        assert "on conflict (fingerprint) do update" in insert_sql.lower()
        assert insert_params[0] == job_fingerprint(jobs[0])
        assert insert_params[14] == "https://x.example/1"
        link_sql, link_params = conn.executed[1]
        assert "job_search_run_jobs" in link_sql
        assert link_params == ("run-1", "job-1")

    def test_upsert_counts_reused_rows_as_duplicates(self) -> None:
        conn = FakeConnection()
        conn.set_rows([{"id": "job-1", "inserted": False}])
        jobs = [make_normalized(original_url="https://x.example/1")]

        result = asyncio.run(upsert_jobs(conn, search_run_id="run-1", jobs=jobs))

        assert result.inserted == 0
        assert result.duplicates == 1

    def test_upsert_deduplicates_before_inserting(self) -> None:
        conn = FakeConnection()
        conn.set_rows([{"id": "job-1", "inserted": True}])
        jobs = [
            make_normalized(original_url="https://x.example/1"),
            make_normalized(original_url="https://x.example/1?utm_source=x"),
        ]

        result = asyncio.run(upsert_jobs(conn, search_run_id="run-1", jobs=jobs))

        assert result.inserted == 1
        assert result.duplicates == 0
        assert len(conn.executed) == 2

    def test_upsert_maps_work_mode_and_employment_type(self) -> None:
        conn = FakeConnection()
        conn.set_rows([{"id": "job-1", "inserted": True}])
        jobs = [
            make_normalized(
                work_mode="on-site",
                employment_type="full-time",
                original_url="https://x.example/1",
            )
        ]

        asyncio.run(upsert_jobs(conn, search_run_id="run-1", jobs=jobs))

        _, params = conn.executed[0]
        assert params[6] == "on-site"
        assert params[7] == "full-time"

    def test_upsert_refreshes_reused_job_metadata(self) -> None:
        conn = FakeConnection()
        conn.set_rows([{"id": "job-1", "inserted": False}])
        jobs = [
            make_normalized(
                company="Updated Acme",
                work_mode="hybrid",
                published_at=datetime(2026, 8, 18, tzinfo=UTC),
                original_url="https://x.example/1",
            )
        ]

        asyncio.run(upsert_jobs(conn, search_run_id="run-1", jobs=jobs))

        insert_sql = conn.executed[0][0].lower()
        assert "company = excluded.company" in insert_sql
        assert "published_at = coalesce(excluded.published_at" in insert_sql
        assert "work_mode = coalesce(excluded.work_mode" in insert_sql


def test_published_at_is_kept_utc() -> None:
    published = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)
    normalized = normalize_job(make_job(published_at=published))
    assert normalized.published_at == published
