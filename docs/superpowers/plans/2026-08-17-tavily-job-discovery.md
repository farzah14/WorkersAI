# Tavily Job Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the wired Brave web-search source with a tested Tavily connector while preserving the existing job-fetching, normalization, deduplication, and matching pipeline.

**Architecture:** Tavily implements the existing `SourceConnector` protocol and returns `DiscoveryCandidateUrl` metadata. The existing SSRF-safe career-page fetcher remains responsible for retrieving job descriptions. Tavily is configured with the server-only `TAVILY_API_KEY`; no SDK or new user-facing provider abstraction is added.

**Tech Stack:** Python 3.12, HTTPX, Pydantic, pytest, pytest-httpx, existing worker source-error taxonomy.

---

### Task 1: Add failing Tavily connector contract tests

**Files:**
- Modify: `apps/worker/tests/test_job_connectors.py`

- [x] **Step 1: Add the Tavily fixtures and tests before implementation**

Add a `TAVILY_URL` constant and a response fixture with `results` containing a valid HTTPS job URL, an HTTP URL, and a result without a URL. Add tests that assert:

```python
async def test_tavily_maps_results_to_candidates(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=TAVILY_URL, json=TAVILY_BODY)
    connector = TavilyConnector(api_key="test-key", client=httpx.AsyncClient())

    candidates = await connector.search(QUERY)

    assert len(candidates) == 1
    assert isinstance(candidates[0], DiscoveryCandidateUrl)
    assert candidates[0].url == "https://careers.acme.com/jobs/data-engineer"
    assert candidates[0].title == "Data Engineer at Acme"
    assert candidates[0].snippet == "Join our data team in Jakarta."
    request = httpx_mock.get_requests()[-1]
    assert request.method == "POST"
    assert request.json()["query"] == QUERY.terms
    assert request.json()["include_answer"] is False
    assert request.json()["include_raw_content"] is False
    assert request.json()["api_key"] == "test-key"
    await connector.aclose()
```

Also add focused tests for an empty key (`SourceConfigError`), HTTP 401/403 (`SourceConfigError`), HTTP 408/429/500 (`SourceUnavailable`), malformed JSON (`SourceDataError`), unexpected `results` shape (`SourceDataError`), and errors not containing the API key.

- [x] **Step 2: Run the focused tests and verify the expected RED state**

Run from `apps\worker`:

```cmd
uv run pytest tests/test_job_connectors.py -k tavily -q
```

Expected result: collection or test failure because `TavilyConnector` does not yet exist. Do not implement production code before observing this failure.

### Task 2: Implement bounded Tavily HTTP and result mapping

**Files:**
- Modify: `apps/worker/jobmatch_worker/jobs/connectors/base.py`
- Create: `apps/worker/jobmatch_worker/jobs/connectors/tavily.py`

- [x] **Step 1: Add a POST JSON helper using the existing error taxonomy**

Add a small `post_json_with_retry` helper beside `get_json_with_retry`. It must use the existing capped-body reader and classify timeouts/transport errors, HTTP 408/429/5xx, and other 4xx exactly like the existing GET helper. Return a reconstructed `httpx.Response` with the capped response body. Export the helper in `__all__`.

- [x] **Step 2: Implement `TavilyConnector`**

Implement `TavilyConnector` with:

```python
TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_DEFAULT_COUNT = 10

class TavilyConnector:
    source_key = "tavily"

    async def search(self, query: SearchQuery) -> list[DiscoveredJob | DiscoveryCandidateUrl]:
        ...
```

The request body must include the query, the API key, `topic="general"`, `search_depth="basic"`, bounded `max_results`, `include_answer=False`, `include_raw_content=False`, and `include_images=False`. Parse only a dictionary containing a list-valued `results` field. Map each result's `url`, `title`, and `content` to `DiscoveryCandidateUrl`; ignore invalid candidates rather than promoting snippets to descriptions. Keep the client lifecycle and error behavior consistent with `BraveConnector`.

- [x] **Step 3: Run the focused Tavily tests and verify GREEN**

```cmd
uv run pytest tests/test_job_connectors.py -k tavily -q
```

Expected result: all Tavily connector tests pass.

### Task 3: Wire Tavily into worker configuration and discovery

**Files:**
- Modify: `apps/worker/jobmatch_worker/config.py:7-35`
- Modify: `apps/worker/jobmatch_worker/handlers/discovery.py:22-57,85-90`
- Modify: `apps/worker/.env.example:32-35`
- Modify: `apps/worker/tests/test_config.py`
- Modify: `apps/worker/tests/test_discovery_handler.py`

- [x] **Step 1: Add configuration and source wiring**

Add `tavily_api_key: str = ""` to `Settings`, document `TAVILY_API_KEY` in `.env.example`, import `TavilyConnector`, map `tavily` to source type `search`, and replace the default `brave` entry in `_build_sources()` with `tavily`. Do not put the supplied secret in any tracked file or example file.

- [x] **Step 2: Add wiring assertions**

Update configuration/source tests to assert `TAVILY_API_KEY` is read and `_build_sources()` returns a `tavily` source while preserving Greenhouse and Lever. Assert the discovery handler records `tavily` provenance and still isolates a source failure.

- [x] **Step 3: Run focused wiring tests**

```cmd
uv run pytest tests/test_config.py tests/test_discovery_handler.py -q
```

Expected result: all focused tests pass.

### Task 4: Verify the complete worker behavior

**Files:**
- No additional production files unless a focused test exposes a Tavily-specific defect.

- [x] **Step 1: Run the complete worker test suite**

```cmd
uv run pytest -q
```

- [x] **Step 2: Run static checks**

```cmd
uv run ruff check .
uv run mypy jobmatch_worker
```

- [ ] **Step 3: Configure local testing without exposing the key**

Add `TAVILY_API_KEY` only to the ignored `apps/worker/.env`, set `REQUIREMENT_EXTRACTION_ENABLED=true`, restart the worker, and run one Indonesia search after the application quota resets. Never commit or paste the value into logs. Revoke and regenerate the key before production use because it was exposed in chat.

- [ ] **Step 4: Verify the local smoke path**

Confirm the run records a `tavily` source outcome, discovers candidate URLs, fetches permitted pages, normalizes jobs, queues requirement extraction, and produces matches. Existing local data and unrelated web worktree changes must remain untouched.
