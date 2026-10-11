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

## Review follow-up (2026-09-09)

The reviewed follow-up commits are `8ffb0a9`, `ba6a88f`, `85de858`, `f489c37`,
`2520ba7`, and `ec2d38e`, on top of the original remediation sequence.

- `supabase/tests/jobs_visibility.sql` now wraps both role privilege checks in
  pgTAP `ok(...)` assertions. PostgreSQL documents `has_table_privilege` with
  two- or three-argument forms; the assertion description is now supplied to
  pgTAP instead of the PostgreSQL function. See the
  [PostgreSQL 15 access-privilege function contract](https://www.postgresql.org/docs/15/functions-info.html#FUNCTIONS-INFO-ACCESS-TABLE).
- Settings component coverage now checks sanitized failure feedback,
  re-enablement, and no refresh after a failed full-deletion response.
- Requirements coverage now checks the exact 100,000-character boundary,
  complete user-prompt delivery at the router boundary, and preservation of an
  existing cache row after extraction failure.
- Browser acceptance now includes the missing-code OAuth callback branch,
  original-only retention, Settings full deletion, account deletion, and a
  gated completed-export download check. The completed-export check verifies
  XLSX magic bytes and filtered worksheet titles, plus PDF magic bytes and
  filtered PDF titles. The test timeout is 180 seconds for its 120-second
  completion poll. It requires `RUN_EXPORT_E2E=1` and a running worker/storage
  environment.

Fresh local rerun after these changes:

| Area | Command | Result |
|---|---|---|
| Worker unit/integration tests | `cd apps/worker && uv run pytest -q` | **Passed: 389 passed, 1 skipped** |
| Worker Ruff | `cd apps/worker && uv run ruff check .` | **Passed** |
| Worker mypy | `cd apps/worker && uv run mypy jobmatch_worker` | **Passed — 49 files** |
| Web tests | `corepack pnpm --dir apps/web test` | **Passed: 19 files, 153 tests** |
| Web lint and TypeScript | `corepack pnpm --dir apps/web lint` and `tsc --noEmit --incremental false` | **Passed** |
| Git whitespace check | `git diff --check` | **Passed** |

The new browser tests were typechecked and linted but not executed because the
normal Playwright command still stops in global setup when `apps/web/.env` is
absent. SQL/RLS and Docker/Compose remain blocked by the missing Supabase CLI
and Docker executables.

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

At the time of the runs above, local code gates were verified but SQL/RLS,
authenticated E2E, and deployment readiness remained unverified. The update
below supersedes the earlier SQL/tooling blocker.

## Local database verification follow-up (2026-09-09)

Verified on `fix/jobs-rls-and-discovery`, based on `2264300` with the
`profiles_ai.sql` fixture correction committed alongside this record.
Docker and the local Supabase instance `matcher_saas` are now available.
No database reset was performed during this follow-up; the SQL suites use
transactions and roll back their synthetic fixtures.

- Reproduced the focused failure: the search-profile fixture referenced the
  nonexistent `title` column, aborting after 13 of 18 planned assertions.
- Corrected the fixture to reference an existing synthetic candidate profile
  and supply the required region and target roles. Strengthened the linkage
  assertion to verify the newly saved, confirmed profile rather than merely
  checking a non-null foreign key. No application code or migrations changed.
- `npx --no-install supabase test db supabase/tests/profiles_ai.sql`:
  **PASS, 1 file / 18 tests, exit 0**.
- `npx --no-install supabase test db`:
  **PASS, 8 files / 301 tests, exit 0**, including `core_cv.sql` and
  `jobs_visibility.sql`.
- `git diff --check`: **PASS**.

On this Ubuntu session, commands were executed through `sg docker -c` to use
the user's existing Docker group membership without restarting the desktop.
These results close the previously missing local SQL/RLS execution evidence.
Authenticated browser flows, Compose validation/build, and real OAuth/provider
verification were not run in this follow-up and remain separate gates.

## Post-merge acceptance follow-up (2026-09-09)

PR #2 merged to `main` at `451d251`. Verification continued from that exact
commit on `codex/fix-post-merge-acceptance`, using only synthetic users and the
disposable local Supabase project `matcher_saas`.

The first authenticated browser run reproduced seven acceptance failures. Six
were stale or state-leaking test assumptions: successful registration now keeps
the session and redirects to `/dashboard`, while the active-CV test selected an
uploaded CV without a confirmed candidate profile and did not reliably restore
the seeded active CV. The fixture and journeys now match the approved product
behavior. Missing `settings.subheading` messages in both locales were also
added and covered by the i18n parity test.

The remaining browser failures exposed two application defects:

- `save_candidate_profile` tried to change `candidate_profile_id` on a current
  search profile already referenced by `job_search_runs`. PostgreSQL correctly
  rejected that mutation through the composite history foreign key. Commit
  `a8c535f` adds an append-only migration that retires the old current row and
  clones its criteria onto a new current search profile linked to the new
  candidate-profile version. The focused pgTAP test failed at the foreign key
  before the migration and passes with 20 assertions after it.
- The export worker received UUID objects from psycopg for `user_id` and
  `search_run_id`, then passed them into string-typed `ExportRequest` fields.
  Commit `f633c1b` normalizes those values at the database boundary. The focused
  production-shaped worker test failed with a UUID/string mismatch before the
  change and passes afterward.

Fresh results after the fixes:

| Area | Command | Result |
|---|---|---|
| Clean migration replay | `npx --no-install supabase db reset --local` | **Passed: all migrations through `202609090001` applied** |
| SQL/RLS | `npx --no-install supabase test db` | **Passed: 8 files / 303 assertions** |
| Authenticated browser suite | `pnpm exec playwright test` | **Passed: 22; skipped: 1 explicitly gated export test** |
| Worker-backed export acceptance | `RUN_EXPORT_E2E=1 pnpm exec playwright test ... --grep "completed exports"` with worker/storage running | **Passed: XLSX and PDF downloads and filtered contents** |
| Web tests | `pnpm test` | **Passed: 19 files / 153 tests** |
| Web lint and TypeScript | `pnpm lint`; `pnpm exec tsc --noEmit` | **Passed** |
| Web production build | `pnpm build` | **Passed: 26 routes** |
| Worker tests | `uv run pytest -q` | **Passed: 389; skipped: 1 optional live AI test** |
| Worker Ruff and mypy | `uv run ruff check .`; `uv run mypy jobmatch_worker` | **Passed: 49 production files** |
| Production Compose | `docker compose -f compose.production.yml config --quiet`; `docker compose -f compose.production.yml build` | **Passed: worker and scheduler images built** |
| Whitespace | `git diff --check` | **Passed** |

The temporary `.env.production` used for quiet Compose validation contained
only local test settings and was removed after the build. Ignored `apps/web/.env`
was not staged. No real CV, production data, or provider quota was used.

These results establish local merge readiness. They do not verify a real Google
OAuth login, live 9Router/model reachability, or an actual staging/production
deployment; those remain external release checks.

## Five-job search limit follow-up (2026-09-09)

The user approved a new MVP rule that each manual or daily discovery run retains
at most five distinct jobs. Commit `97ae966` applies the limit after
normalization and deduplication and before persistence, provenance, requirement
extraction, and matching.

- RED: the new seven-distinct-job regression persisted all seven jobs.
- GREEN: it persists the first five jobs, records five provenance rows, queues
  five requirement-extraction items, reports `discovered_count=7` and
  `normalized_count=5`, and keeps `duplicate_count=0`.
- `uv run pytest tests/test_discovery_handler.py -q`: **13 passed**.
- `uv run pytest -q`: **390 passed, 1 optional live-AI test skipped**.
- `uv run ruff check .`: **passed**.
- `uv run mypy jobmatch_worker`: **passed, 49 source files**.
- `git diff --check`: **passed**.
