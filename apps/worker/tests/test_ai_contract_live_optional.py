"""Opt-in live AI provider contract tests.

These tests call the real 9Router endpoint and consume model quota,
so they are skipped unless ``RUN_LIVE_AI_TESTS=1`` is set.
Ordinary CI never runs them. The test builds a 9Router router and
asserts that the gateway returns Pydantic-schema-valid structured output
for the candidate profile extraction contract.
"""

import os

import pytest

from jobmatch_worker.ai.router import AiRouter
from jobmatch_worker.config import Settings
from jobmatch_worker.handlers.profile import build_ai_providers
from jobmatch_worker.profiles.extract import extract_candidate_profile
from jobmatch_worker.profiles.models import CandidateProfile

LIVE = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_AI_TESTS") != "1",
    reason="live AI tests are opt-in via RUN_LIVE_AI_TESTS=1",
)

SAMPLE_CV_TEXT = (
    "Jane Doe\nSoftware Engineer\n"
    "Python, SQL, ETL, BigQuery\n"
    "Worked on data pipelines and analytics platforms for 5 years.\n"
)


def _router_for(settings: Settings, provider_name: str) -> AiRouter:
    providers = [
        provider for provider in build_ai_providers(settings) if provider.name == provider_name
    ]
    if not providers:
        pytest.skip(f"{provider_name} is not configured (missing key or model)")
    return AiRouter(providers, operation="live_contract_test")


def _assert_valid_profile(result: object) -> None:
    assert isinstance(result, CandidateProfile), f"unexpected profile type: {type(result)}"
    assert result.target_roles, "profile must include at least one target role"
    assert result.skills, "profile must include at least one skill"


@LIVE
@pytest.mark.asyncio
async def test_live_ninerouter_profile_contract() -> None:
    settings = Settings()  # type: ignore[call-arg]
    profile = await extract_candidate_profile(
        SAMPLE_CV_TEXT, _router_for(settings, "9router")
    )
    _assert_valid_profile(profile)
