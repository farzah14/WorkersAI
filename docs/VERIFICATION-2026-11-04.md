# Discovery Preferences and Result Filters — Verification Record

**Verification date:** 2026-11-04
**Branch:** `feat/discovery-preferences-and-result-filters`
**Plan:** `docs/superpowers/plans/2026-11-03-discovery-preferences-and-result-filters.md`

This record separates code-level evidence from infrastructure-dependent acceptance. No production database, live provider quota, or real user CV was used.

## Implemented behavior

- Discovery applies normalized work-mode, employment-type, and literal excluded-keyword preferences before deduplication and the five-job cap. Unknown work-mode/employment-type metadata remains eligible during discovery.
- Dashboard filters add title/company query, employment type, exact source, work mode, publication dates, and explicit ignored visibility. Dates are inclusive; invalid or reversed ranges keep the last valid filters, show a localized error, and disable export.
- The dashboard match query is scoped to the latest run (decision D1) and passes that run ID to the table export action.
- Dashboard exports serialize the active filters into the existing array-based export contract, including `exclude_ignored` for the default All-status view.
- Web and worker export filters share NFC + whitespace-collapse + lowercase query matching, with a regression proving `strasse` does not match `Straße`.
- XLSX and PDF criteria summaries record query, employment type, source, and ignored-row handling.

## Fresh local gates

| Area | Command | Result |
|---|---|---|
| Worker focused preferences | `cd apps/worker && uv run pytest tests/test_job_preferences.py -q` | **Passed: 21 tests** |
| Worker focused discovery | `cd apps/worker && uv run pytest tests/test_discovery_handler.py -q` | **Passed: 35 tests** |
| Worker focused exports | `cd apps/worker && uv run pytest tests/test_export_service.py tests/test_excel_export.py tests/test_pdf_export.py -q` | **Passed: 44 tests** |
| Worker full suite | `cd apps/worker && uv run pytest -q` | **Passed: 477 passed, 1 skipped** |
| Worker Ruff | `cd apps/worker && uv run ruff check .` | **Passed** |
| Worker mypy | `cd apps/worker && uv run mypy jobmatch_worker` | **Passed: 52 source files** |
| Web full suite | `cd apps/web && pnpm test` | **Passed: 25 files, 221 tests** |
| Web typecheck | `cd apps/web && pnpm typecheck` | **Passed** |
| Web lint | `cd apps/web && pnpm lint` | **Passed** |
| Whitespace | `git diff --check` | **Passed** |

The skipped worker test is the existing opt-in live AI contract test. It does not prove gateway reachability.

## Synthetic acceptance coverage

Named focused tests cover P1–P10 and F1–F9 from the plan:

- discovery: selected/empty/unknown work modes and employment types, literal exclusions (`C++`, `java`/JavaScript, whitespace/case), filtering before the cap, eligible provenance, completed empty run, partial empty run, both regions;
- results: combined query/type/source, unknown metadata exclusion, default hidden ignored rows, clear/reset, inclusive and reversed dates, `Straße`/`strasse`, NFC spelling parity, export serialization;
- exports: strict unknown-key rejection, employment enum and source/query bounds, reversed dates, legacy date-only and timestamp normalization, all-scope compatibility, ignored/status AND semantics, XLSX/PDF membership and criteria summaries, cross-user run rejection at the API boundary.

## Browser acceptance

| Area | Command | Result |
|---|---|---|
| Playwright suite | `cd apps/web && pnpm exec playwright test` | **BLOCKED before seed** |
| Completed export artifacts | `RUN_EXPORT_E2E=1` with worker/storage | **NOT RUN** |

Playwright requires a disposable Supabase target. This environment has no Docker daemon and no running local Supabase (`127.0.0.1:54321` unreachable). The only configured Supabase project is remote, so pointing the seed at it would mutate non-disposable data. The new browser journeys in `apps/web/e2e/dashboard.spec.ts` were typechecked and linted but not executed.

## SQL/RLS acceptance

| Area | Command | Result |
|---|---|---|
| pgTAP/RLS suites | `supabase test db` against disposable local Supabase | **BLOCKED** |

The Supabase CLI exists, but no local database is running and Docker is unavailable. No reset or test was run against the remote project.

## Follow-up to unblock

1. Start a disposable local Supabase (Docker + `supabase start`) and create an ignored `apps/web/.env` pointing at it.
2. Run `supabase test db`, then `pnpm --dir apps/web exec playwright test`.
3. Start the worker/storage stack and run the gated completed-export test with `RUN_EXPORT_E2E=1`, then clear the variable.
