# WorkersAI Verification Record

**Verification date:** 2026-09-09 (Asia/Jakarta)
**Reviewed branch:** `fix/jobs-rls-and-discovery`
**Reviewed commit at local-gate run:** `19750d4` and its committed ancestors through the remediation sequence

This record distinguishes fresh local evidence from checks blocked by missing infrastructure. Commands were run against synthetic/local test fixtures. No production database, real user account, provider quota, or private CV was used.

## Fresh local gates

| Area | Command | Result |
|---|---|---|
| Worker unit/integration tests | `cd apps/worker && uv run pytest -q` | **Passed: 387 passed, 1 skipped** |
| Worker lint | `cd apps/worker && uv run ruff check .` | **Passed: All checks passed** |
| Worker type check | `cd apps/worker && uv run mypy jobmatch_worker` | **Passed: 49 source files, no issues** |
| Web tests | `corepack pnpm --dir apps/web test` | **Passed: 19 files, 152 tests** |
| Web lint | `corepack pnpm --dir apps/web lint` | **Passed** |
| Web TypeScript | `corepack pnpm --dir apps/web exec tsc --noEmit --incremental false` | **Passed** |
| Web production build | `corepack pnpm --dir apps/web build` | **Passed: 26 routes generated** |
| Whitespace | `git diff --check` | **Passed** |
| Optional live AI contract | Included in worker suite | **Skipped by gate; `RUN_LIVE_AI_TESTS` was not enabled** |

The skipped worker test is intentionally quota-free behavior. It does not prove gateway reachability or production model compatibility.

## Blocked integration gates

| Area | Command | Result and unblock condition |
|---|---|---|
| Local Supabase reset | `supabase db reset --local` | **Blocked:** `supabase` executable is not installed. Install the Supabase CLI and target a disposable local instance. |
| pgTAP SQL suites | `supabase test db` | **Blocked:** same missing Supabase CLI; run after local reset on the disposable instance. |
| Production Compose validation | `docker compose -f compose.production.yml config --quiet` | **Blocked:** `docker` executable is not installed. Install Docker/Compose and validate without printing secret values. |
| Compose image build | `docker compose -f compose.production.yml build` | **Not run:** Docker unavailable. |
| Authenticated Playwright | `corepack pnpm --dir apps/web exec playwright test` | **Blocked before seed:** `apps/web/.env` is absent. Supply an ignored test-only web environment pointing to disposable Supabase, then rerun. |
| Optional live 9Router contract | `cd apps/worker && RUN_LIVE_AI_TESTS=1 uv run pytest tests/test_ai_contract_live_optional.py -q` | **Not run:** requires an explicitly configured test gateway/model and authorized quota. |

The Playwright command started the Next.js web server successfully, then global setup failed while reading `apps/web/.env`; no seed users or database mutations were made.

## Required follow-up sequence

1. Install/configure local Supabase and Docker, confirm the target is disposable, then run `supabase db reset --local` and `supabase test db`. This must execute the new `supabase/tests/jobs_visibility.sql` suite and the updated `job_discovery.sql` assertion.
2. Create an ignored `apps/web/.env` with local Supabase URL, publishable key, service-role key, and database URL. Run the authenticated Playwright suite, including cross-user isolation and CV deletion flows.
3. Validate `compose.production.yml` and build the worker image with a staging-only `.env.production`; ensure the 9Router URL is reachable from the container network.
4. Enable the live AI test only when a test gateway/model and quota are intentionally available. Record pass or skip separately from normal CI.

Until those steps are completed, local code gates are verified but SQL/RLS, authenticated E2E, and deployment readiness remain unverified.
