# Tavily Job Discovery Connector

## Status

Approved design for replacing Brave Search with Tavily in the worker's web
discovery path. Implementation is local-first; production configuration is a
separate deployment step.

## Scope

Use Tavily's documented search API to discover candidate job URLs for Indonesia
and Global searches. Keep the existing career-page fetcher, normalization,
canonicalization, deduplication, requirement extraction, matching, and source
isolation behavior unchanged.

This does not add direct integrations with JobStreet, Indeed, Kalibrr, Glints,
or KitaLulus. Tavily discovers permitted public URLs; the existing HTTPS and
robots-aware career-page fetcher retrieves job text.

## Decision

Add a `TavilyConnector` that implements the existing `SourceConnector`
protocol. Use HTTPX directly, matching the current connectors and avoiding a
new SDK dependency. Wire Tavily as the web-search source in place of Brave.

The connector sends one bounded search request per generated `SearchQuery` and
maps each valid Tavily result to `DiscoveryCandidateUrl`. Search result content
is metadata only and must never be promoted to a job description. The existing
career-page fetcher remains responsible for obtaining visible job text.

The source key and provenance value are `tavily`. Existing Greenhouse and Lever
connectors remain available. Brave's connector and tests remain as isolated
code, but Brave is no longer wired into the default discovery source map.

## Configuration

Add the server-only `TAVILY_API_KEY` setting. The key is read from the worker's
ignored `.env` file for local testing and from the production worker secret
environment during deployment. It must not appear in source files, examples,
logs, test fixtures, or committed files.

Use a fixed documented Tavily search endpoint and a bounded result count. Do not
add a provider-selection abstraction or a user-facing provider setting for this
change.

## Data Flow

1. The existing query builder appends `Indonesia` for Indonesia-region runs.
2. `TavilyConnector.search()` submits the query to Tavily with answer and raw
   content expansion disabled.
3. The connector validates the response shape and maps result title, URL, and
   content snippet to candidate URL metadata.
4. The existing discovery handler canonicalizes candidate URLs and uses the
   SSRF-safe, robots-aware career-page fetcher.
5. Existing normalization and deduplication persist canonical jobs and source
   provenance before downstream AI work is queued.

## Error Handling

- Empty API key or rejected credentials produce `SourceConfigError` with source
  key `tavily`.
- Timeouts, transport failures, HTTP 408, HTTP 429, and HTTP 5xx responses
  produce retryable `SourceUnavailable` errors.
- Invalid JSON, unexpected response shapes, or invalid result data produce
  `SourceDataError`.
- Error messages must not contain the API key, request body, raw snippets, or
  full provider responses.
- A Tavily failure remains isolated and may make a run `partial`; it must not
  discard usable results from Greenhouse, Lever, or other sources.

## Testing

Add mocked HTTP contract tests before implementation for:

- valid result mapping and Indonesia query forwarding;
- invalid or non-HTTPS result URLs being ignored by model validation;
- missing API key returning `SourceConfigError`;
- HTTP 401/403 returning configuration errors;
- HTTP 408/429/5xx returning `SourceUnavailable`;
- malformed JSON and malformed result shapes returning `SourceDataError`;
- API keys not appearing in raised error messages;
- discovery source wiring using `tavily` and preserving partial-source
  isolation.

Run the focused connector and discovery tests, then the complete worker test
suite, Ruff, and mypy. A live API smoke test is optional and must use the local
ignored secret only.

## Rollout

1. Add the connector and tests without changing the existing web UI.
2. Configure `TAVILY_API_KEY` in the local worker environment and restart the
   worker.
3. Run one Indonesia search after the application quota resets and verify
   Tavily source success, normalized jobs, requirement extraction, and matches.
4. Configure the same setting separately in the production worker environment
   only after hosted database counts, RLS, storage privacy, and deployment
   smoke tests pass.
5. Revoke and regenerate the key that was pasted into chat before production
   use.

## Out of Scope

- Direct job-board scraping or undocumented private endpoints.
- Tavily extract, crawl, map, or research endpoints.
- JavaScript execution in the career-page fetcher.
- A generic multi-provider search abstraction.
- Automatic migration of local CV/profile data into hosted production.
