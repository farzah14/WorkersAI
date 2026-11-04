# Discovery Preferences and Result Filters — Implementation Plan

**Date:** 2026-11-03
**Status:** Approved and implemented on `feat/discovery-preferences-and-result-filters`; local code gates pass. Browser and SQL/RLS acceptance remain blocked pending disposable infrastructure (see `docs/VERIFICATION-2026-11-04.md`).
**Execution edition:** Expanded 2026-11-04 for a lower-cost coding model. Read sections 8–12 before executing tasks.
**Goal:** Respect existing discovery preferences and let users narrow matched results with consistent filtered exports.
**Dependencies:** The six original MVP milestones remain authoritative and ordered. Before implementation, verify their applicable acceptance gates; this document does not certify milestone completion.

> **User-directed UI change (2026-11-04):** The dashboard export card was removed. Export requests and history remain on `/exports`; this supersedes the dashboard filtered-export UI requirement below. API and worker export-filter contracts remain unchanged.

## 1. Authority and boundaries

Follow `AGENTS.md`, the approved `2026-08-16-ai-job-matcher-saas-design.md`, and the approved `2026-09-09-five-job-search-limit-design.md`. The filtering semantics below are proposed clarifications for review, not an already approved replacement specification. Reconcile any conflict before coding.

Keep Next.js, Supabase, the PostgreSQL queue, Python worker, and 9Router. Reuse existing connectors, filters, exports, translations, and tests. No new dependency or database migration is expected for this scope.

Included:

- Consistent employment-type, work-mode, and excluded-keyword preferences in discovery.
- Result search by title/company, employment-type and source filters.
- Expose existing work-mode and publication-date filtering in the UI.
- Reuse existing table sorting; preserve deterministic default ordering.
- Export the same selected-run result set as the active dashboard filters.
- English and Bahasa Indonesia labels, validation, and accessible controls.

Deferred: salary filtering, new source integrations, saved filter presets, notifications, richer application stages, result-cap changes, and selecting the best five through extra AI scoring. Salary needs a separate contract for currency, pay period, and missing values; the current normalized model has no pay-period field. Do not present minimum salary as an enforced discovery constraint in this phase; clarify the existing control in both locales.

## 2. Verified starting points

- `apps/web/lib/search/schema.ts` accepts employment types, work modes, and excluded keywords, as well as optional salary preferences.
- `apps/worker/jobmatch_worker/handlers/discovery.py` currently loads work modes and exclusions, but not employment types or salary. Exclusions reach connector queries without a shared final exclusion predicate.
- `apps/worker/jobmatch_worker/jobs/query.py` builds bounded queries; connector hints are not authoritative post-fetch filtering.
- `apps/web/lib/jobs/filter.ts` already implements region, work mode, score, status, and publication-date filtering.
- `apps/web/components/jobs/filters.tsx` currently exposes region, status, and minimum score only.
- `apps/web/components/jobs/match-table.tsx` already sorts by score, title, company, and date. It owns filter state and hides ignored rows by default.
- `apps/web/app/exports/page.tsx` requests exports for the latest run without dashboard filter state. `ExportRequestForm` already accepts a filter payload.
- IMPORTANT: the dashboard loads the latest run for its header, but its match query currently loads matches across all of the user's runs and deduplicates by job. Do not assume the table is already scoped to the latest run. See section 8 for the proposed behavior change requiring approval.
- Export API validation and Python export filtering are separate contracts and both require updates.
- Worker configuration currently defaults `max_jobs_per_run` to five and allows overrides. This feature will not alter that setting; tests exercise the approved five-job default.

Earlier analysis overstated the sorting gap: sorting exists. Source filtering in this plan uses the job's primary `source_name`, not all provenance sources.

## 3. Proposed behavior contract

### Discovery

1. Query configured sources with existing bounds, retries, URL safety, and partial-source isolation.
2. Preserve existing freshness, Indonesia eligibility, and regional ordering behavior.
3. Normalize results, then apply a small shared preference predicate before deduplication and the existing run cap. Preserve relative order of eligible jobs.
4. Employment type and work mode: empty preference arrays impose no restriction. Known values outside a selected set are rejected. Unknown values remain eligible to avoid losing valid jobs with incomplete metadata; communicate this policy in the preference UI.
5. Exclusions: trim/casefold and collapse whitespace. Match each nonempty phrase as literal normalized substring in title, company, or description. Any match rejects the job. No regex, stemming, or AI interpretation. Test substring behavior explicitly so users are not promised whole-word matching.
6. Retain deduplication and provenance for eligible jobs. An ineligible duplicate must not displace an eligible representation. Do not merge claims or invent missing fields to satisfy a preference.
7. Persist and enqueue only the eligible retained jobs. Filtering must happen before the cap so rejected jobs cannot consume slots.
8. Keep existing counters: discovered means source results; normalized means retained jobs; duplicate means actual duplicates among eligible normalized candidates. Rejected preferences and cap omissions are not duplicates or source failures.
9. Zero eligible jobs with successful sources is an empty successful run, or partial when some sources failed, using existing status rules. Do not retry merely because preferences removed all results.
10. Manual and daily runs use the same predicate. Historical runs and shared canonical records are not retroactively rewritten.

### Dashboard

- Add `query` (trimmed, maximum 200 characters), `employment_type`, and `source_name` to the validated filter contract.
- Query matches a case-insensitive literal substring in title OR company. Combine different filter fields with AND.
- Employment type and source use exact canonical values. Derive source options from the full selected-run rows before applying filters; no invented source allowlist.
- Unlike discovery preferences, an explicit result field filter excludes rows with unknown values. Default All includes unknowns.
- Expose work mode and publication dates with labeled native inputs. Dates are inclusive calendar dates; reject invalid dates and reversed ranges in the validated contract.
- Keep ignored rows hidden by default; explicit Ignored shows them. Centralize this effective selection rule so exports agree.
- Clear resets all filter fields. Reset the visible-row count when filters change. Show a localized filtered result count and useful empty state.
- Existing sorting remains. Add a stable tie-break where needed; do not change scoring or bucket thresholds.

### Exports

- Add a filtered-export action beside the dashboard table, bound to its selected run ID and active filter state. Avoid a second independent copy of filter state; pass `runId` into `MatchTable` and reuse `ExportRequestForm` there if that remains the smallest solution.
- Use one explicit serializer to convert dashboard single selections into the export API's existing array fields. Add bounded query, employment-type, source, and explicit default-hidden-ignored behavior to both API and Python contracts.
- The exported membership equals all matching rows for that run, not just the first visible page. XLSX and PDF have identical membership. Export order continues using the existing deterministic score order; custom table sort order is not promised.
- Exports read current persisted tracking state when generated. A status change between request and execution can change membership; no snapshot system is introduced.
- Keep the standalone exports page's All behavior and existing queued export compatibility. New fields must be optional with backward-compatible defaults. Encode ignored-row exclusion explicitly for dashboard requests rather than changing legacy exports globally.
- Continue deriving ownership from authentication and rechecking run ownership server-side. Reject arbitrary filter keys; never interpolate filter text into SQL.

## 4. Execution tasks, in order

For each behavior: write focused tests, observe the intended failure, implement the minimum change, then rerun focused and broader affected checks. Commit coherent units only after checks pass. Use a feature branch and preserve unrelated changes.

### Task 0 — Preflight and contract approval

- [x] Obtain approval of this scope and the proposed unknown-field, exclusion, and export semantics.
- [x] Inspect actual branch/status and applicable `AGENTS.md` files. Read installed Next.js guides before frontend changes.
- [x] Confirm original milestone acceptance evidence and run applicable baseline checks; stop for unrelated blocking failures.
- [x] Inspect database types, export queries, E2E fixtures, and every caller of modified filter helpers before changing contracts.
- [x] If implementation reveals a required migration or a specification conflict, revise this plan before proceeding. No migration was required.

### Task 1 — Enforce discovery preferences

Files:

- New: `apps/worker/jobmatch_worker/jobs/preferences.py` and `apps/worker/tests/test_job_preferences.py`.
- Modify: `apps/worker/jobmatch_worker/handlers/discovery.py`, `apps/worker/tests/test_discovery_handler.py`.
- Modify preference help copy in `apps/web/messages/en.json` and `apps/web/messages/id.json`, plus the existing search form if required.

- [x] Add pure predicate tests for all selected/empty/unknown work-mode and employment-type combinations; exclusions in all three fields; casing, whitespace, literal punctuation, and blank exclusions.
- [x] Add handler tests proving employment types are loaded, filtering precedes the cap, rejected jobs receive no persistence or downstream work, and eligible duplicates retain provenance.
- [x] Cover both regions, manual/daily-equivalent payloads, retries, mixed source failures, and zero eligible jobs. Assert counters and source status semantics.
- [x] Extend the run SELECT, invoke the predicate on normalized jobs, and reuse existing queue/persistence logic.
- [x] Run focused and full worker tests, Ruff, and mypy.

### Task 2 — Expand the result filter contract and controls

Files:

- Modify: `apps/web/lib/jobs/filter.ts`, `apps/web/components/jobs/filters.tsx`, `apps/web/components/jobs/match-table.tsx`.
- Modify: `apps/web/tests/job-filter.test.ts`, `apps/web/tests/match-table.test.tsx`, `apps/web/tests/i18n.test.ts`.
- Modify: `apps/web/messages/en.json`, `apps/web/messages/id.json`.

- [x] Add focused tests for combined query/type/source filters, unknowns, validation bounds, inclusive dates, reversed ranges, and default ignored behavior.
- [x] Extend defaults, parsing, application, and reset behavior together. Preserve existing callers and filter tests.
- [x] Add labeled native controls, stable source options, localized feedback, and filtered count; reuse current sort controls.
- [x] Verify keyboard operation and reset behavior through component tests and browser acceptance.

### Task 3 — Connect filtered exports end to end

Files:

- Modify: `apps/web/app/dashboard/page.tsx`, `apps/web/components/jobs/match-table.tsx`, `apps/web/components/export-request-form.tsx`, `apps/web/app/api/exports/route.ts`.
- Modify: `apps/worker/jobmatch_worker/exports/models.py`, `apps/worker/jobmatch_worker/exports/service.py`.
- Modify: `apps/web/tests/export-request.test.ts`, `apps/web/tests/export-request-form.test.tsx`, `apps/web/tests/match-table.test.tsx`, `apps/worker/tests/test_export_service.py`.
- Add a small filter serializer test beside existing web filter tests if needed; update translations for the dashboard action.

- [x] Test dashboard serializer, selected-run identity, strict input validation, optional legacy defaults, and explicit ignored handling.
- [x] Extend worker export projections with employment type only where missing. Reuse existing title, company, and source fields.
- [x] Employment type is already present in `ExportRow` and `load_rows`; do not add it again. Extend `SearchCriteria`, `criteria_from_request`, and the XLSX/PDF criteria summaries for the new filter fields.
- [x] Add shared synthetic filter cases in the existing test suites: the same IDs must survive web and worker filtering, including unknown values and Unicode casing edge cases. Specify one consistent comparison rule where JavaScript and Python differ.
- [x] Verify XLSX/PDF membership, all-results-in-filter behavior, empty export behavior, legacy requests, and unauthorized run rejection.

### Task 4 — Acceptance and documentation

Files:

- Modify: `apps/web/e2e/dashboard.spec.ts` and/or `apps/web/e2e/mvp.spec.ts` using existing synthetic fixtures.
- Modify: `docs/TESTING.md` and the relevant user-facing preference help; append fresh verification evidence to a dated record.

- [ ] Browser journey: synthetic run, combined filters, source and employment type, unknown metadata, dates, clearing, sort reuse, and both locales. Authored in `apps/web/e2e/dashboard.spec.ts`; blocked by missing disposable Supabase.
- [ ] Worker-backed export journey: request from the filtered dashboard and inspect downloaded XLSX/PDF contents; keep infrastructure-dependent acceptance gated. Not run; worker/storage unavailable.
- [ ] Confirm another user's run/data remains inaccessible. Run existing SQL/RLS suites against disposable local Supabase if available; no reset of an unverified database target. API-boundary ownership test passes; SQL/RLS blocked.
- [x] Record source/unit, SQL/RLS, browser, export artifact, and optional live-provider evidence separately. Do not claim full completion if required acceptance remains blocked. See `docs/VERIFICATION-2026-11-04.md`.

## 5. Verification commands

Run from repository root in Windows CMD after dependencies are installed:

```bat
pnpm --dir apps\web test
pnpm --dir apps\web lint
pnpm --dir apps\web typecheck
cd apps\worker
uv run pytest tests/test_job_preferences.py tests/test_discovery_handler.py tests/test_export_service.py -q
uv run pytest -q
uv run ruff check .
uv run mypy jobmatch_worker
cd ..\..
pnpm --dir apps\web exec playwright test
git diff --check
```

For completed-export acceptance, configure only the existing disposable test environment, start its worker/storage, and use CMD syntax `set RUN_EXPORT_E2E=1` before the relevant Playwright test; clear it afterward with `set RUN_EXPORT_E2E=`. Inspect the actual E2E gate before running. Normal checks must not consume external AI or discovery quota.

If available against a confirmed disposable local instance, use the installed project Supabase CLI to run `supabase test db`. Builds, installation, deployment, live provider calls, and publishing are outside this planning request.

## 6. Acceptance checklist

- [x] Known incompatible jobs and literal excluded phrases are rejected consistently across connectors.
- [x] Unknown metadata follows the documented discovery/result distinction.
- [x] Filtered-out jobs cannot consume the five-job default cap or receive downstream AI work.
- [x] Discovery deduplication, provenance, retries, regional safeguards, and partial results remain intact.
- [x] Every new result filter combines correctly with existing filters and clear/reset behavior.
- [ ] Dashboard-filtered XLSX/PDF membership agrees with the selected run and effective filters. Unit/artifact membership parity passes; end-to-end artifact download remains blocked.
- [x] Existing exports, authorization, privacy, and bilingual accessibility remain intact.
- [x] Fresh focused/broader tests and affected lint/type checks pass; browser/artifact checks have recorded results.
- [x] No implementation, migration, deployment, or live-quota work occurs during plan creation. (Historical planning constraint; implementation happened only after approval.)

## 7. Evidence available at planning time

Read-only baseline from this conversation: web 24 files / 191 tests passed; worker 432 passed / 1 optional live AI test skipped; `git diff --check` passed. These are baseline results, not evidence that proposed features exist. Current browser, SQL/RLS, deployment, and live discovery acceptance were not run during this review.

## 8. Decision gate: dashboard and export scope

**Decision D1 (approved 2026-11-04):** scope the dashboard match query to the same latest run displayed in its header by adding `.eq("search_run_id", run.id)` alongside authenticated ownership filtering. Pass that exact `run.id` into the table/export action. No run picker or cross-run export is included.

This changes existing behavior: older-run matches will no longer appear in the main dashboard. Saved and application pages retain their existing tracking behavior. The UI must say results are for the latest search, in both languages. This change makes dashboard membership and run-scoped export membership consistent without adding a cross-run export architecture.

Before implementing Task 2 or Task 3, obtain explicit approval of D1 as part of plan approval. If the user wants the current all-history dashboard retained, revise this plan first: do not ship a latest-run export labeled as exporting all visible matches. Do not silently add an all-history API or filter displayed matches only at export time.

Test D1 with two synthetic runs belonging to one user and a third run belonging to another user. Put different jobs in each run and the same job with different match records in both own runs. The dashboard and its export must contain only the displayed latest run's rows, using that run's scores. Existing owner isolation must still hold.

## 9. Exact contracts for implementation

These names are the intended contract. Reuse existing equivalents where present; do not introduce parallel filter systems.

### 9.1 Discovery helper

Add one pure function in `jobs/preferences.py`:

```python
def matches_preferences(
    job: NormalizedJob,
    *,
    work_modes: Sequence[str],
    employment_types: Sequence[str],
    excluded_keywords: Sequence[str],
) -> bool:
    ...
```

Use `Sequence` from `collections.abc`, existing `NormalizedJob`, and existing `normalize_text`. No database calls, logging of descriptions, network calls, AI, or mutation in this helper. Test normalized strings independently of SQL fakes.

Extend `_RUN_SELECT_SQL` with `sp.employment_types`. The actual SQL column must exist before coding; inspect the search-profile migration. Production rows should use that selected field; update every synthetic run fixture to include it rather than hiding a missing projection with a permissive fallback.

Insert preference filtering inside the existing normalization loop or immediately after it. Pass the eligible list to existing deduplication. Ensure `_persist_provenance(all_jobs=...)` receives eligible normalized records so rejected representations are not reintroduced into run-specific provenance. Do not modify global canonical jobs merely to remove one user's rejected result.

### 9.2 Frontend internal representation

Extend `MatchFilters` with `query: string`, `employmentType: "all" | EmploymentType`, and `sourceName: string | null`. Use `null` for All sources so a real source named `all` does not collide with a sentinel. Reuse/export the employment-type vocabulary from `lib/search/schema.ts` if it can be imported safely; do not invent new enum values.

Defaults: `query = ""`, `employmentType = "all"`, `sourceName = null`; retain existing defaults for other fields. Wire keys remain snake case (`employment_type`, `source_name`), while `query` stays unchanged. `parseMatchFilters` must keep rejecting unknown keys.

Query normalization for dashboard and exports: trim, normalize Unicode to NFC, then lowercase using JavaScript `toLowerCase()` and Python `lower()`. Collapse internal whitespace consistently in both implementations. No locale-sensitive casing, accent removal, transliteration, or `casefold()` for this cross-runtime query comparison. In particular, query `strasse` does not match title `Straße`; add a regression. Discovery exclusions continue using existing Python `normalize_text` casefold behavior because they do not share a browser predicate.

Validate query length by Unicode code points after normalization: at most 200 (`Array.from(value).length` in JavaScript, `len(value)` in Python). Bound source names to 200 code points and reject empty/whitespace-only names. Source matching remains exact and case-sensitive; do not lowercase source identifiers.

Centralize ignored visibility in `applyMatchFilters`: All status hides ignored rows; explicit Ignored selects them. Remove the redundant table-only predicate once tests cover this change. Inspect every caller before changing this helper's default behavior.

### 9.3 Export wire representation

Example request generated by the dashboard serializer:

```json
{
  "searchRunId": "11111111-1111-4111-8111-111111111111",
  "format": "xlsx",
  "scope": "current_filters",
  "filters": {
    "query": "engineer",
    "employment_type": ["full-time"],
    "source_name": ["greenhouse"],
    "work_mode": ["remote"],
    "min_score": 70,
    "exclude_ignored": true
  }
}
```

New optional export fields: `query: string`, `employment_type: EmploymentType[]` (maximum 8 entries), `source_name: string[]` (maximum 20 entries, each bounded as above), `exclude_ignored: boolean` (default false for legacy requests). Empty arrays mean unrestricted, matching existing export conventions. Dashboard serialization emits one-element arrays only for selected values and omits unrestricted fields. Do not send `all`, null source selections, or frontend camelCase keys.

Dashboard All status: omit `status` and set `exclude_ignored = true`. Explicit status: send its one-element `status` array and set `exclude_ignored = false`. Treat the boolean and status predicates as AND if an external caller supplies both; never let one silently override the other.

Use the existing API body-size limit, strict Zod object, and Python `extra="forbid"`. Validate new bounds and employment enums in both runtimes. Reject reversed date ranges. Preserve legacy accepted ISO datetime inputs at the API boundary by converting them to UTC calendar dates before queue persistence; do not pass raw datetime strings into Python date fields. New dashboard controls send `YYYY-MM-DD` only. Cover old date-only requests and timestamp normalization separately.

Add new fields to `SearchCriteria` so generated reports describe active filters, and populate them in `criteria_from_request`. Update `exports/excel.py` and `exports/pdf.py` criteria summaries plus `test_excel_export.py` and `test_pdf_export.py`. Escape user text using existing report safety helpers. No new job columns are needed: `ExportRow` and the SQL already contain employment type, company, title, and primary source.

### 9.4 UI details

- Keep filter state in `MatchTable`; no global store or new context provider.
- Add a required `runId` prop only if all callers are updated; inspect tests and other pages first. No fallback to a newly fetched latest run when requesting exports.
- Source options come from unfiltered `rows`, unique and sorted; exact source values are preserved. Do not derive them from currently displayed results.
- Reuse existing native sort controls. Filtered export guarantees membership, not custom sort order.
- Disable dashboard export while an optimistic status update or removal is pending. On failure, restore the previous state using existing behavior. Explain that exports use persisted state at generation time; do not promise a snapshot.
- Empty filter result: display zero and the existing localized empty-state pattern; allow Clear. Disable filtered-export buttons for zero matches, while retaining the worker's safe empty-report behavior for races or direct requests.
- Validate date ranges visibly; do not silently swap dates. Keep last valid effective filters while date input is invalid, show a localized error, and disable export until corrected. Add a minimal separate draft state only for dates if necessary.
- Scope labels, new field labels, option labels, unknown-metadata help, salary limitation help, Clear, counts, and errors must have synchronized English/Indonesian keys. Do not rewrite unrelated page copy.

## 10. Small execution cards for a lower-cost model

Execute one card at a time. A card is finished only when its focused checks pass. The broader gates in section 5 still apply before completion. These cards refine Tasks 0–4; they do not start a second implementation sequence.

| Card | Deliverable | Focused command from repository root (CMD) | Completion evidence |
|---|---|---|---|
| C0 | Approved D1 and contracts; clean baseline or documented unrelated changes; feature branch | `git status --short --branch` | Record branch, approval, and exact baseline results |
| C1 | Pure discovery predicate and table-driven tests | `cd apps\worker` then `uv run pytest tests/test_job_preferences.py -q` | Observe missing-helper failure, then all cases pass |
| C2 | Run projection, fixtures, eligible filtering, cap/provenance/counter regression | From `apps\worker`: `uv run pytest tests/test_discovery_handler.py -q` | Assert persisted job identities and queued work, not only counts |
| C3 | Frontend defaults/parser/predicate and serializer tests | `pnpm --dir apps\web test -- tests/job-filter.test.ts` | Cases from section 11 pass; no new UI yet |
| C4 | Filter controls, scope query D1, translations and table integration | `pnpm --dir apps\web test -- tests/match-table.test.tsx tests/i18n.test.ts` | Input/reset/error behavior and two-run scope regression pass |
| C5 | Strict export API and serializer request integration | `pnpm --dir apps\web test -- tests/export-request.test.ts tests/export-request-form.test.tsx tests/match-table.test.tsx` | Exact run ID/payload, ownership rejection, pending/empty disabled behavior |
| C6 | Worker export predicate, criteria summaries, legacy compatibility | From `apps\worker`: `uv run pytest tests/test_export_service.py tests/test_excel_export.py tests/test_pdf_export.py -q` | Web/worker memberships agree; both artifacts record criteria |
| C7 | Browser acceptance, complete affected gates, verification document | Section 5 commands and gated export E2E | Record PASS/FAIL/BLOCKED/NOT_RUN per evidence layer |

After worker commands, return to repository root with `cd ..\..` before using root-relative commands. Inspect actual test runner argument handling before copying focused commands. Do not install missing dependencies or reset a database to make a card appear green without checking the task's authorization and target first.

Prefer these coherent commit boundaries after applicable checks: discovery predicate/integration; frontend contract/controls; export API/worker/integration; acceptance/docs. A commit is optional while work is incomplete; do not commit intentionally broken intermediate API/worker contracts. Never stage `.env` or unrelated dirty files.

## 11. Mandatory synthetic acceptance examples

Use these examples as named focused tests in existing suites. They are behavioral checks, not permission to create a second test framework.

| ID | Input | Expected |
|---|---|---|
| P1 | Preference remote; job on-site | Reject discovery |
| P2 | Preference remote; job work mode null | Keep discovery; result filter Remote excludes it |
| P3 | Employment full-time; job internship | Reject discovery |
| P4 | Employment array empty; job internship | Keep discovery |
| P5 | Exclusion `senior engineer`; description `SENIOR   ENGINEER required` | Reject discovery |
| P6 | Exclusion `C++`; title `C++ Developer` | Reject as literal substring; no regex error |
| P7 | Exclusion `java`; title `JavaScript Developer` | Reject under documented substring semantics |
| P8 | Seven distinct jobs: first two incompatible, next five eligible | Persist the next five; enqueue only those five; normalized count five; duplicate count zero |
| P9 | All results rejected; one successful source, none failed | Completed empty run; no preference-driven retry |
| P10 | All results rejected; one successful and one failed source | Partial empty run under existing source status rules |
| F1 | Query `acme`, title `Engineer`, company `ACME Labs` | Include |
| F2 | Query `engineer`, source greenhouse, type full-time | Include only rows satisfying all three |
| F3 | Remote selected; mode null; published-date filter selected; date null | Exclude; unknown fields never satisfy explicit filters |
| F4 | All status; ignored row | Hidden in dashboard and dashboard-filtered export |
| F5 | Ignored explicitly selected | Included if other filters match |
| F6 | Clear after changing every field | Defaults restored, date draft errors cleared, visible count reset |
| F7 | Date from after date to | Visible validation; export disabled; API rejects direct invalid payload |
| F8 | Query `strasse`, title `Straße Engineer` | No match in either web or worker export |
| F9 | Composed and decomposed accented spelling of same query/title | Equal after NFC normalization |
| E1 | Active table contains run A; newer run B created after page load | Export request remains tied to A, never silently switches to B |
| E2 | Legacy scope all with no new fields and an ignored row | Existing all-export membership unchanged |
| E3 | Seven synthetic matching rows, five initially visible | Export all seven if all satisfy filters; fixture can bypass production cap to test paging |
| E4 | Other user's run ID | API rejects; no export row or work item created for that request |
| E5 | Filter contains SQL-looking text or unknown object keys | Text treated literally; unknown keys rejected; no SQL interpolation |
| E6 | Same filters in XLSX and PDF | Same included job identities and recorded criteria |
| E7 | Pending optimistic status request | Export disabled until persisted success or rollback |

For membership parity fixtures, compare stable synthetic job identifiers in test helpers or distinct original URLs. Do not add a production job-ID field solely to satisfy a test. Use synthetic report data only.

## 12. Copyable handoff prompt and stop rules

Use this prompt only after approving implementation and D1:

```text
Implement docs/superpowers/plans/2026-11-03-discovery-preferences-and-result-filters.md.
The approved scope includes decision D1 and sections 3 and 9. Follow AGENTS.md.
Read the whole plan once, then execute C0 through C7 sequentially using TDD.
Do not skip the existing milestone gates. Do not delegate or spawn subagents.
Use existing libraries, helpers, tests, connectors, and UI conventions.
Preserve unrelated work. No new dependencies, schema changes, live quota calls,
builds, deployments, or pushes are requested. Do not change the run limit.
For each card report changed paths and focused verification briefly.
If blocked, report the exact failing command, sanitized decisive error,
whether the failure existed before your edits, and the smallest required decision.
Final report must separate code checks, SQL/RLS, browser journeys, and generated
export evidence. Do not claim success for unrun or blocked acceptance checks.
```

Stop rather than improvise if D1 is not approved, the actual schema differs from required fields, an unrelated baseline failure blocks verification, a migration is required, ownership must be weakened, a source requires unclear permissions, or the implementation would need a deferred feature. For routine coding choices already covered by this plan, proceed without asking again. User approval persists across execution cards.

When resuming after context loss, read this plan, `git status`, and the latest verification note; identify the last completed card from fresh evidence. Do not infer completion from unchecked prose or repeat destructive setup. Update task checkboxes only after their relevant checks pass.
