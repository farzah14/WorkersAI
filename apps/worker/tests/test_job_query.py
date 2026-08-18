import pytest

from jobmatch_worker.jobs.query import SearchQuery, build_queries


def test_indonesia_query_mentions_country_and_role() -> None:
    q = build_queries(region="indonesia", roles=["Data Engineer"], locations=["Jakarta"])
    assert any("Data Engineer" in x and "Jakarta" in x and "Indonesia" in x for x in q)


def test_global_query_supports_remote() -> None:
    q = build_queries(region="global", roles=["Data Engineer"], locations=[], remote=True)
    assert any("remote" in x.lower() for x in q)


def test_build_queries_returns_search_query_objects() -> None:
    q = build_queries(region="global", roles=["Data Engineer"], locations=["Jakarta"])
    assert all(isinstance(x, SearchQuery) for x in q)


def test_build_queries_caps_at_six_queries() -> None:
    roles = ["Data Engineer", "Data Analyst", "Data Scientist", "ML Engineer", "BI Engineer"]
    locations = ["Jakarta", "Bandung", "Surabaya"]
    q = build_queries(region="global", roles=roles, locations=locations)
    assert len(q) <= 6


def test_build_queries_caps_remote_fallback_queries_at_six() -> None:
    q = build_queries(
        region="indonesia",
        roles=["Data Engineer", "Data Analyst", "Data Scientist"],
        locations=["Jakarta", "Bandung"],
        remote=True,
    )

    assert len(q) <= 6


def test_build_queries_uses_top_three_roles() -> None:
    roles = ["Data Engineer", "Data Analyst", "Data Scientist", "ML Engineer"]
    locations = ["Jakarta"]
    q = build_queries(region="global", roles=roles, locations=locations)
    assert len(q) == 3
    assert all("Data Engineer" in x for x in q[:1])
    assert all("ML Engineer" not in x for x in q)


def test_build_queries_uses_at_most_two_locations() -> None:
    roles = ["Data Engineer"]
    locations = ["Jakarta", "Bandung", "Surabaya"]
    q = build_queries(region="global", roles=roles, locations=locations)
    assert len(q) == 2


def test_build_queries_filters_blank_roles_and_locations() -> None:
    q = build_queries(region="global", roles=["Data Engineer", "  ", ""], locations=["", "Jakarta"])
    assert len(q) == 1
    assert "Data Engineer" in q[0]


def test_build_queries_rejects_empty_roles() -> None:
    with pytest.raises(ValueError):
        build_queries(region="global", roles=[], locations=["Jakarta"])
    with pytest.raises(ValueError):
        build_queries(region="global", roles=["  "], locations=["Jakarta"])


def test_build_queries_deduplicates_roles_case_insensitively() -> None:
    q = build_queries(region="global", roles=["Data Engineer", "data engineer"], locations=["Jakarta"])
    assert len(q) == 1


def test_build_queries_region_is_case_insensitive() -> None:
    q_upper = build_queries(region="INDONESIA", roles=["Data Engineer"], locations=["Jakarta"])
    q_lower = build_queries(region="indonesia", roles=["Data Engineer"], locations=["Jakarta"])
    assert str(q_upper[0]) == str(q_lower[0])
    assert "Indonesia" in q_upper[0]


def test_build_queries_rejects_unknown_region() -> None:
    with pytest.raises(ValueError):
        build_queries(region="mars", roles=["Data Engineer"], locations=["Jakarta"])


def test_excluded_keywords_become_negative_terms() -> None:
    q = build_queries(
        region="global",
        roles=["Data Engineer"],
        locations=["Jakarta"],
        excluded_keywords=["senior", "lead", ""],
    )
    assert q[0].negative_terms == ("senior", "lead")


def test_negative_terms_absent_when_no_exclusions() -> None:
    q = build_queries(region="global", roles=["Data Engineer"], locations=["Jakarta"])
    assert q[0].negative_terms == ()


def test_remote_not_duplicated_when_already_present() -> None:
    q = build_queries(region="global", roles=["Data Engineer"], locations=["remote"], remote=True)
    assert q[0].terms.count("remote") == 1


def test_no_location_produces_role_only_query() -> None:
    q = build_queries(region="global", roles=["Data Engineer"], locations=[])
    assert len(q) == 1
    assert q[0].terms == "Data Engineer"


def test_remote_location_search_adds_countrywide_fallback() -> None:
    q = build_queries(
        region="indonesia",
        roles=["Robotics Teacher"],
        locations=["Jakarta"],
        remote=True,
    )

    assert q[0].terms == "Robotics Teacher Jakarta Indonesia remote"
    assert q[1].terms == "Robotics Teacher Indonesia remote"


def test_query_builder_caps_excluded_keywords() -> None:
    q = build_queries(
        region="global",
        roles=["Data Engineer"],
        locations=[],
        excluded_keywords=[f"exclude-{index}" for index in range(20)],
    )
    assert len(q[0].negative_terms) == 10


def test_query_builder_rejects_oversized_search_terms() -> None:
    with pytest.raises(ValueError):
        build_queries(region="global", roles=["x" * 201], locations=[])
