# WorkersAI Audit Remediation Implementation Plan

> **For agentic workers:** Use the `executing-plans` skill to implement this plan task by task. Steps use unchecked boxes to track work. Complete and verify one task before starting the next; honor any user instruction to stop after a numbered task.

**Goal:** Repair every confirmed defect from the September 8 audit and close the unfinished acceptance checks without expanding MVP scope.

**Architecture:** Preserve Next.js 16, Supabase Auth/PostgreSQL/private Storage, the durable PostgreSQL queue, and the Python worker. All generative AI continues through the provider-neutral router backed by 9Router. Canonical jobs are shared; candidate data, matches, tracking, and exports remain user-owned.

**Tech stack:** TypeScript, Next.js, Vitest, Playwright, Python 3.12+, pytest, Ruff, mypy, PostgreSQL, pgTAP, Supabase, Docker Compose.

**Status:** Code fixes and executable regression coverage are complete on the audited feature branch. Mandatory SQL/RLS, authenticated browser, and Docker/provider checks remain verification-blocked. The execution table below is the authoritative status; unchecked step boxes are retained as the original task checklist, while the table records the actual red/green and verification boundaries.

**Execution update (2026-09-09):** Tasks 1 through 9 were implemented and
committed on `fix/jobs-rls-and-discovery`. Review follow-up commits corrected
the pgTAP privilege assertions, added the Settings failure-state regression,
covered the requirements boundary/cache failure cases, and expanded browser
acceptance coverage for OAuth callback routing, CV retention/deletion, export
downloads, and account deletion. Task 3 remains verification-blocked until
the CV SQL/RLS suite runs. Task 4 remains verification-blocked until the
corrected SQL suite runs. Task 10 remains verification-blocked because
Supabase CLI, Docker/Compose, and the authenticated Playwright environment
are unavailable. The local worker/web gates pass with the new tests.
Task 11 is now reconciled in this plan, the verification record, and the
historical checklist; the remaining open items are explicit Task 3, Task 4,
and Task 10 verification boundaries.

## 1. Baseline and scope

Repository: `/home/farzah/Downloads/WorkersAI`.

Audit snapshot: September 8, 2026, current branch `fix/jobs-rls-and-discovery`, commit `bdc3b1c`.

| Ref | Snapshot | Relationship |
|---|---|---|
| `fix/jobs-rls-and-discovery` | `bdc3b1c` | Current checkout; one commit above local main |
| `main` | `12de9c3` | 24 commits above locally recorded origin/main |
| `codex/audit-critical-high-remediation` | `12de9c3` | Same tree as local main |
| `origin/main` | `e58a023` | Local remote-tracking snapshot; no fetch performed |

One worktree existed during the audit. Preserve the pre-existing untracked `docs/PROJECT_ANALYSIS_REPORT.md`; do not overwrite or include it in an implementation commit accidentally.

| Gate | Audit evidence | Meaning |
|---|---|---|
| Worker pytest | 371 passed, 1 skipped | Local suite passed; live contract skipped |
| Worker mypy | Passed, 48 source files | Static typing passed |
| Worker Ruff | Failed: I001, SIM102, SIM103 | Required quality gate is broken |
| Web Vitest | 150 passed, 18 files | Local web suite passed |
| Web lint and TypeScript | Passed | Static web checks passed |
| Web production build | Passed | Application builds |
| Git whitespace checks | Passed | No whitespace errors in reviewed diffs |
| SQL/RLS and migrations | Not executed | Docker/Supabase tooling unavailable |
| Authenticated Playwright | Not executed | Disposable seeded integration environment not verified |
| Production Compose and provider reachability | Not verified | Build success is not deployment evidence |

These are historical baseline results, not proof that any future implementation is finished. Re-run affected gates after each change.

## 2. Finding-to-task coverage

| Finding or unfinished item | Classification | Task |
|---|---|---|
| Old provider architecture remains in specification and deployment instructions | Documentation/configuration defect | 1 |
| Three Ruff failures | Quality gate failure | 2 |
| Settings promises full deletion but sends original-only deletion | Product defect inherited from main | 3 |
| jobs RLS migration contradicts existing SQL assertion | Acceptance defect introduced on current branch | 4 |
| x.com substring blocks legitimate employer domains | Discovery defect introduced on current branch | 5 |
| Short Open Graph descriptions become job locations | Data quality defect introduced on current branch | 6 |
| Requirements after character 15,000 disappear | Matching defect introduced on current branch | 7 |
| Default configuration does not extract requirements for new jobs | Product/configuration defect inherited from main | 8 |
| Export bucket and daily scheduling environment names do not match settings | Configuration defect inherited from main | 9 |
| Database, browser, deployment, and optional provider checks lack evidence | Unfinished verification, not automatically broken code | 10 |
| Previous completion checklist overstates readiness | Status/documentation defect | 11 |

The audit reproduced individual function behavior with synthetic inputs. It did not prove a production incident or inspect production user data.

Do not reopen fixes already present merely because an older report lists them: scheduler returning identifiers, quota ownership enforcement, CV upload compensation, signup session retention, atomic profile save, removal of the two-job limit, hybrid provenance, export controls, and terminal run accounting. Retain their regression coverage and investigate only fresh failures.

Do not treat a partially failed source as a new confirmed bug: the discovery handler retains successful jobs, uses partial run status, and retries sources only when no usable jobs remain. Preserve that behavior.

## 3. Execution contract

- Work on a feature branch based on the audited current branch, never directly on main/master. At execution time, inspect `git status`, `git branch --show-current`, and `git worktree list`; select an isolated checkout if another task is editing the current one.
- Read `AGENTS.md` and applicable nested instructions. Before web changes, read the relevant installed Next.js documentation required by `apps/web/AGENTS.md`.
- Task 1 reconciles documented architecture before product changes. Subsequent tasks repair foundation/privacy, discovery, matching, then hardening; do not skip an earlier failing acceptance gate to claim a later milestone complete.
- For each behavior fix: write a focused regression, confirm the intended failure, implement the minimum repair, pass focused and broader affected tests, pass lint/types, review, run `git diff --check`, then commit only that task's files.
- For documentation and mechanical lint fixes, inspect the exact diff and run relevant checks; do not invent meaningless tests.
- Record unavailable infrastructure as blocked verification. Do not substitute mocks for SQL ownership or authenticated browser acceptance.
- Shared migrations are append-only. Do not disable RLS or rewrite migration `202609060004_jobs_rls_policy.sql` to satisfy an obsolete test.
- Use only synthetic fixtures. Keep secrets, raw CV text, signed URLs, and service-role credentials out of commits and verification notes.
- Commands below run from repository root unless a `cd` is shown. They are Windows CMD-compatible. `uv` and Supabase/Docker must be installed in the execution environment; the audit's Linux fallback used `apps/worker/.venv/bin/python -m ...` for Python checks.
- Stop for a decision if a change requires weakening security, destroying user data, violating the approved product scope, or bypassing an unrelated failing acceptance gate.

## Task 1: Reconcile documentation with the approved 9Router architecture

**Priority:** High; documentation prerequisite.

**Files to modify:**
- `docs/superpowers/specs/2026-08-16-ai-job-matcher-saas-design.md`
- `docs/superpowers/plans/README.md`
- `docs/superpowers/plans/2026-08-16-ai-router-and-candidate-profile.md`
- `docs/DEVELOPMENT.md`
- `docs/DEPLOYMENT.md`
- `.env.example`

**Read for authority:** `AGENTS.md`, `docs/AI-PROVIDERS.md`, `apps/worker/jobmatch_worker/config.py`, `apps/worker/jobmatch_worker/handlers/profile.py`, `compose.production.yml`, and `apps/worker/tests/test_ai_contract_live_optional.py`.

- [ ] Search active operational documentation for removed NVIDIA/OpenRouter/Ollama configuration. Preserve explicitly historical records; correct instructions that claim to describe the current runtime.
- [ ] Replace the active provider configuration with this contract, without selecting a permanent business-logic model:

```dotenv
AI_PROVIDER_ORDER=9router
AI_TIMEOUT_SECONDS=30
NINEROUTER_BASE_URL=http://localhost:20128/v1
NINEROUTER_API_KEY=
NINEROUTER_MODEL=replace-with-configured-model-id
NINEROUTER_EMBED_MODEL=
RUN_LIVE_AI_TESTS=0
```

- [ ] Document that the model must be configured; an API key is optional only when the gateway permits keyless access. Preserve application JSON parsing, schema validation, bounded retries, and deterministic lexical degradation when embeddings are unset.
- [ ] Explain that `localhost:20128` inside a worker container refers to that container. Production must supply a reachable gateway URL for its actual topology; do not claim the default proves host-gateway reachability or add an unrequested public gateway.
- [ ] Correct the root example's `ENABLE_LIVE_AI_TESTS` name to the test's actual `RUN_LIVE_AI_TESTS` gate. Check whether other example-only variables have consumers before claiming they control behavior. Do not add speculative logging/retry features to justify unused example variables.
- [ ] Keep all command examples CMD-compatible, or label Linux VPS commands explicitly. Document the separate worker and web environment files and the required worker `SUPABASE_URL`.
- [ ] Review the resulting documents against AGENTS.md, run `git diff --check`, and commit as `docs: align deployment and design with 9Router`.

**Done when:** A fresh developer following active setup instructions configures the current provider interface; the approved design and active plans no longer prescribe removed adapters. This task documents connectivity requirements; Task 10 verifies them.

## Task 2: Restore the worker lint gate

**Priority:** Medium; required verification prerequisite.

**Files to modify:**
- `apps/worker/jobmatch_worker/exports/service.py`
- `apps/worker/jobmatch_worker/jobs/connectors/career_page.py`
- `apps/worker/jobmatch_worker/jobs/connectors/tavily.py`

- [ ] Reproduce the three failures:

```bat
cd apps\worker
uv run ruff check .
```

Expected baseline: I001 in export imports, SIM102 in the Open Graph fallback, SIM103 in the final Tavily condition; nonzero exit.

- [ ] Move `from psycopg import AsyncConnection` into third-party imports before first-party imports.
- [ ] Mechanically combine the nested Open Graph condition without changing its behavior yet; Task 6 removes the defective fallback.
- [ ] Replace the final Tavily `if ...: return False; return True` with:

```python
return not re.search(r"\bjob\s+opportunities\s+(?:in|di)\b", title_text)
```

- [ ] Run `uv run ruff check .`, `uv run mypy jobmatch_worker`, and `uv run pytest -q`. Expect no lint/type errors and no failing tests.
- [ ] Return to root, review the diff, run `git diff --check`, and commit as `chore: restore worker lint gate`.

**Done when:** All three reported errors are gone with no product behavior changes.

## Task 3: Make Settings deletion honor its full-deletion promise

**Priority:** High; privacy and user expectation.

**Modify:** `apps/web/app/settings/settings-actions.tsx`.

**Create:** `apps/web/tests/settings-actions.test.tsx`.

**Existing regression files:** `apps/web/tests/cv-upload.test.ts`, `apps/web/tests/account-delete.test.ts`, `apps/web/tests/i18n.test.ts`, `supabase/tests/core_cv.sql`.

**Read:** `apps/web/app/api/cvs/route.ts`, `apps/web/components/cv-delete-button.tsx`, and Settings copy in `apps/web/messages/en.json` and `apps/web/messages/id.json`.

- [ ] Add a React test using the existing export-form test's jsdom, fetch mock, and `next/navigation` mock pattern. Render `SettingsActions` with `cv={{ id: "cv-1", original_name: "synthetic.pdf" }}` and a complete copy object. Click Delete and assert:

```typescript
const [input, init] = fetchMock.mock.calls[0];
const url = new URL(String(input), window.location.origin);
expect(url.pathname).toBe("/api/cvs");
expect(url.searchParams.get("cv_id")).toBe("cv-1");
expect(url.searchParams.get("mode")).toBe("full");
expect(init.method).toBe("DELETE");
```

- [ ] Run `corepack pnpm --dir apps/web exec vitest run tests/settings-actions.test.tsx`; confirm it fails because `mode` is absent.
- [ ] Add the explicit parameter immediately after `cv_id`:

```typescript
url.searchParams.set("mode", "full");
```

- [ ] Cover failed HTTP responses: show the sanitized error, re-enable the action, and do not refresh on failure. Cover success refreshing the page. Restore global fetch mocks and clean up rendered components between tests.
- [ ] Preserve the separate original-only action and API default. Full deletion must use `delete_cv`; original-only deletion must retain profile/matches and enforce extraction readiness.
- [ ] Run the new component test plus CV, account-delete, and i18n tests; then the full web suite, lint, and typecheck. Run the CV SQL suite on the disposable environment before marking privacy behavior fully accepted.
- [ ] Review, run `git diff --check`, and commit as `fix: request full CV deletion from Settings`.

**Done when:** Settings deletes the CV record, original file, and dependent profile/matches through the existing authorized full-deletion route; the original-retention control continues to preserve structured data. SQL acceptance unavailable means this task remains verification-blocked, not fully complete.

**Review correction (2026-09-09):** The `mode=full` request and successful-refresh
coverage are present. The component suite now also verifies sanitized failure
feedback, action re-enablement, and no refresh after a failed response. The
task is still verification-blocked because the disposable Supabase CV/RLS
acceptance suite has not run.

## Task 4: Align SQL acceptance tests with shared authenticated jobs access

**Priority:** High; database acceptance failure.

**Modify:** `supabase/tests/job_discovery.sql`.

**Create:** `supabase/tests/jobs_visibility.sql` for isolated role-behavior assertions.

**Read only:** `supabase/migrations/202609060004_jobs_rls_policy.sql`, earlier jobs visibility/grant migrations, and existing isolation fixtures in `supabase/tests/job_discovery.sql`.

- [ ] On a disposable local Supabase instance, apply the migration chain and reproduce the assertion expecting `jobs.rowsecurity = false`.
- [ ] Replace that assertion with:

```sql
select is(
    (select rowsecurity from pg_tables
     where schemaname = 'public' and tablename = 'jobs'),
    true,
    'shared jobs catalog uses authenticated read RLS'
);
```

- [ ] Add a transactional pgTAP test that inserts a synthetic canonical job using service privileges, then checks this role matrix with actual queries:

| Role | SELECT canonical job | INSERT/UPDATE/DELETE catalog | Other user's matches/tracking |
|---|---|---|---|
| authenticated user A | Allowed | Denied or changes zero rows under existing grants/RLS | Hidden |
| authenticated user B | Allowed, same shared job | Denied or changes zero rows | Hidden |
| anon | No job data returned; existing privilege denial is acceptable | Denied | Hidden |
| service_role | Allowed | Allowed for worker persistence | Administrative access as designed |

- [ ] Use `set local role`, transaction-local JWT claims, role resets, and rollback as in the existing suite. Assert the job remains unchanged after denied mutations. Do not grant production DML privileges merely to make a test execute. Match pgTAP planned assertion counts exactly.
- [ ] Verify `jobs_authenticated_select` exists for authenticated SELECT with the intended shared predicate. Retain ownership tests for matches, tracking, run-job associations, and provenance.
- [ ] Run `supabase test db` after `supabase db reset --local` on the disposable instance. Expect no assertion failures; never run a reset against a linked or production database.
- [ ] Commit as `test: verify authenticated shared jobs visibility` after review and whitespace checks.

**Done when:** Fresh database execution proves both the intended shared catalog access and user-owned isolation. The published migration remains unchanged unless a separately evidenced policy defect requires a new append-only migration.

**Review correction (2026-09-09):** The two role-privilege checks in
`jobs_visibility.sql` call PostgreSQL's three-argument `has_table_privilege`
and pass their descriptions through pgTAP `ok(...)`. This removes the static
SQL defect; execution is still required before the task can be marked complete.

## Task 5: Match blocked domains at hostname boundaries

**Priority:** Medium; silent discovery loss.

**Modify:** `apps/worker/jobmatch_worker/jobs/connectors/tavily.py`.

**Test:** `apps/worker/tests/test_job_connectors.py`.

- [ ] Add parameterized regression cases for `jobs.netflix.com`, `careers.spacex.com`, `careers.fedex.com`, and `jobs.straitsx.com`:

```python
@pytest.mark.parametrize("host", [
    "jobs.netflix.com", "careers.spacex.com",
    "careers.fedex.com", "jobs.straitsx.com",
])
def test_tavily_allows_employer_domain_suffixes(host: str) -> None:
    from jobmatch_worker.jobs.connectors.tavily import _is_allowed_job_result
    assert _is_allowed_job_result(f"https://{host}/jobs/123", "Software Engineer")
```

- [ ] Run `uv run pytest tests/test_job_connectors.py -k tavily -q` from `apps/worker`; confirm the new cases fail.
- [ ] Separate true blocked domains from the intentional synthetic `leverdemo` marker. Normalize case and a terminal DNS dot. Match domain entries using:

```python
host == domain or host.endswith("." + domain)
```

- [ ] Keep the demo-marker behavior separate so the hostname fix does not admit existing synthetic fixtures. Preserve HTTPS, closed-page, title, and listing-page checks.
- [ ] Test rejection of `x.com`, `www.x.com`, mixed-case and terminal-dot equivalents, blocked domain subdomains, and existing aggregator fixtures. Test a hostname merely containing a blocked domain string is not rejected by that domain rule alone.
- [ ] Run all connector/discovery tests, Ruff, mypy, and the full worker suite. Commit as `fix: match blocked job domains at hostname boundaries`.

**Done when:** Legitimate suffix-sharing employers survive filtering while actual blocked domains and subdomains remain excluded.

## Task 6: Stop treating generic descriptions as locations

**Priority:** Medium; incorrect normalized data.

**Modify:** `apps/worker/jobmatch_worker/jobs/connectors/career_page.py`.

**Test:** `apps/worker/tests/test_job_connectors.py` and `apps/worker/tests/test_discovery_handler.py`.

- [ ] Add the regression:

```python
def test_generic_og_description_is_not_a_location() -> None:
    html = b'''<html><head><title>Engineer - Acme</title>
    <meta property="og:description"
    content="Join our engineering team and build great products.">
    </head><body><h1>Engineer</h1><p>Build software.</p></body></html>'''
    content = _extract_page_content(html, source_key="career_page")
    assert content.location is None
```

- [ ] Run `uv run pytest tests/test_job_connectors.py -k location -q`; confirm the new test fails with the tagline as its actual value.
- [ ] Remove the entire short-`og:description` location fallback. Retain explicit JobPosting location, labeled job location text, and existing location elements. Unknown location stays `None`; do not infer a city from marketing copy.
- [ ] Verify the existing Greenhouse application-format fixture still yields `Jakarta, Indonesia`; verify explicit location wins over conflicting generic metadata. Check unknown location propagates without becoming a manufactured location string.
- [ ] Run connector/discovery tests, worker lint/types, and the broader worker suite. Commit as `fix: require location evidence in career metadata`.

**Done when:** Generic descriptions never populate location and supported explicit location extraction still passes.

## Task 7: Preserve complete requirements and retire truncated cache entries

**Priority:** High; misleading critical gaps and verdicts.

**Modify:**
- `apps/worker/jobmatch_worker/matching/prompt.py`
- `apps/worker/jobmatch_worker/matching/requirements.py`
- `apps/worker/jobmatch_worker/handlers/discovery.py`
- `apps/worker/jobmatch_worker/handlers/matching.py`

**Create:** `apps/worker/jobmatch_worker/matching/cache_key.py` for the shared extraction-version key.

**Tests:** `apps/worker/tests/test_requirements.py`, `apps/worker/tests/test_discovery_handler.py`, `apps/worker/tests/test_matching_handler.py`, `apps/worker/tests/test_golden_matching.py`.

**Chosen repair:** Send the complete description accepted by the existing 100,000-character discovery bound, rather than silently sending its first 15,000 characters. Keep bounded provider errors and failure accounting; do not fabricate success if the configured model cannot accept that input. No unbounded chunking or new provider architecture is part of this task.

- [ ] Add a prompt regression and confirm the current slice loses the tail:

```python
def test_requirements_prompt_preserves_tail() -> None:
    from jobmatch_worker.matching.prompt import build_requirements_user_prompt
    text = "Company background. " * 900 + "MUST HAVE: active nursing license."
    assert text in build_requirements_user_prompt(text)
```

- [ ] Replace the slicing builder with:

```python
def build_requirements_user_prompt(job_text: str) -> str:
    text = job_text.strip()
    return f"Extract the employment requirements from this job description text.\n\nJob text:\n{text}"
```

- [ ] Keep empty-text validation and enforce the 100,000-character upper bound at extraction entry too, using `PermanentAiError` with a sanitized fixed message for oversized historical/direct inputs. Test the boundary, over-bound input, and that no provider call/cache write occurs on rejection.
- [ ] Introduce this shared key helper so old truncated extractions cannot remain valid cache hits:

```python
import hashlib

def requirements_cache_key(description: str) -> str:
    versioned = "requirements-v2\0" + description
    return hashlib.sha256(versioned.encode("utf-8")).hexdigest()
```

- [ ] Replace the independent raw-description hash calculations in discovery and matching with the helper. In requirement extraction, derive the key from the description actually loaded from the database, rather than trusting an old queued hash. Use that same effective key for cache lookup/write and downstream dedupe keys. This is an extraction-cache version; do not change canonical job fingerprints or provenance.
- [ ] Extend the fake router to capture user prompts. Test complete tail delivery, legacy-key cache miss, new-key cache hit, and an old queued payload against a changed current description. A provider/validation failure must not overwrite a valid cache with an incomplete result.
- [ ] Verify a failed oversized/provider extraction finalizes run accounting correctly and successful jobs in the same batch remain available. Preserve MUST HAVE/PREFERRED/NICE TO HAVE criticality and all scoring weights.
- [ ] Run requirements, discovery, matching-handler, golden matching, and the full worker suites plus lint/types. Commit as `fix: preserve full job requirements and version extraction cache`.

**Done when:** Supported descriptions reach extraction intact; old truncated cache entries are refreshed on subsequent processing; no partial extraction is presented as complete. Existing saved match results are not automatically rewritten: record this rollout boundary and use a new search to regenerate results. Any bulk historical recomputation is a separate operational decision.

**Review correction (2026-09-09):** Requirements tests now accept exactly
100,000 characters, capture the complete user prompt at the router boundary,
and verify that a provider failure leaves an existing cache row untouched.

## Task 8: Enable requirement extraction in the default completed MVP flow

**Priority:** High; new discoveries otherwise produce no matches.

**Modify:** `apps/worker/jobmatch_worker/config.py`, `apps/worker/.env.example`, `.env.example`, `docs/DEVELOPMENT.md`, `docs/DEPLOYMENT.md`.

**Tests:** `apps/worker/tests/test_config.py`, `apps/worker/tests/test_discovery_handler.py`.

- [ ] Update the default-settings expectation from False to True and run `uv run pytest tests/test_config.py -q` to confirm the intended failure. Clear the relevant environment variable and disable dotenv loading in this test so local configuration cannot mask the default.
- [ ] Change the setting and both examples:

```python
requirement_extraction_enabled: bool = True
```

```dotenv
REQUIREMENT_EXTRACTION_ENABLED=true
```

- [ ] Remove the obsolete example comment claiming the requirement handler is not deployed. Explain that explicit false is a discovery-only operator switch; it is not a successful complete matching setup.
- [ ] Test default-config discovery with an empty requirement cache: enqueue extraction, leave the run processing, and eventually enqueue matching. Retain explicit-false coverage and the existing behavior that valid cached requirements can still be matched when extraction is disabled.
- [ ] Test that repeated discovery does not duplicate downstream work. Use realistic query result fields in database doubles.
- [ ] Run config/discovery tests, full worker tests, Ruff, and mypy. Commit as `fix: enable requirement extraction by default`.

**Done when:** A new installation using the documented defaults sends newly discovered jobs through extraction and matching, subject to configured provider availability.

## Task 9: Make documented worker environment names effective

**Priority:** Medium; ignored operator configuration.

**Modify:** `apps/worker/jobmatch_worker/config.py`, `.env.example`, `apps/worker/.env.example`, `docs/DEVELOPMENT.md`, `docs/DEPLOYMENT.md`.

**Test:** `apps/worker/tests/test_config.py`, `apps/worker/tests/test_scheduler.py`, `apps/worker/tests/test_export_service.py`.

**Contract:** Canonical names are `EXPORTS_BUCKET` and `DAILY_DISCOVERY_HOUR_JAKARTA`. Continue accepting the previously documented singular/ASIA names for compatibility. Canonical values win when both are set.

- [ ] Add hermetic parameterized tests for canonical-only, legacy-only, neither, and conflicting environment variables. Legacy-only hour 12 must yield 12, and legacy-only bucket `custom-exports` must yield that bucket. Confirm those two currently fail.
- [ ] Use `AliasChoices` while preserving construction by Python field name:

```python
from pydantic import AliasChoices, Field, model_validator

exports_bucket: str = Field(
    default="exports",
    validation_alias=AliasChoices("EXPORTS_BUCKET", "EXPORT_BUCKET"),
)
daily_discovery_hour_jakarta: int = Field(
    default=7,
    ge=0,
    le=23,
    validation_alias=AliasChoices(
        "DAILY_DISCOVERY_HOUR_JAKARTA", "DAILY_DISCOVERY_HOUR_ASIA_JAKARTA"
    ),
)
model_config = SettingsConfigDict(
    env_file=".env", extra="ignore", populate_by_name=True
)
```

- [ ] Test both hour bounds, invalid hours, and explicit constructor keyword use. Clear both aliases between cases; do not read a developer's private dotenv in tests.
- [ ] Show canonical names in both environment examples and document legacy compatibility. Ensure the worker example contains its required `SUPABASE_URL`, distinct from the web's public variable.
- [ ] Verify scheduler and export consumers receive the resolved settings. Run config, scheduler, export-service, full worker, lint, and type checks. Commit as `fix: accept documented worker environment aliases`.

**Done when:** Supported documented variables actually control export storage and scheduling, with tested precedence and no silent hour fallback.

## Task 10: Close integration and deployment verification gaps

**Priority:** Required release evidence; unavailable tooling is not itself a source defect.

**Existing files:** `supabase/config.toml`, `supabase/tests/*.sql`, `apps/web/playwright.config.ts`, `apps/web/e2e/global-setup.ts`, `apps/web/e2e/mvp.spec.ts`, `apps/web/e2e/dashboard.spec.ts`, `compose.production.yml`, `infra/worker/Dockerfile`, `apps/worker/tests/test_ai_contract_live_optional.py`.

**Create evidence file:** `docs/VERIFICATION-2026-09-08.md`. Record actual execution dates inside it, even if work occurs later.

- [ ] Establish a disposable integration environment with Docker, Supabase CLI, browser dependencies, and synthetic users. Confirm the target is local/test before any reset or seed operation. Playwright global setup creates users and deletes/recreates seed rows, so never aim it at production.
- [ ] Run and record each command independently with exit code and summary:

```bat
supabase start
supabase db reset --local
supabase test db
corepack pnpm --dir apps/web test
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web build
corepack pnpm --dir apps/web exec playwright test
cd apps\worker
uv run pytest -q
uv run ruff check .
uv run mypy jobmatch_worker
cd ..\..
docker compose -f compose.production.yml config --quiet
docker compose -f compose.production.yml build
git diff --check
```

- [ ] Store credentials only in ignored environment files. Use `config --quiet` so expanded secret values are not printed. Start worker/scheduler only against a staging/test database and a configured reachable gateway, then inspect sanitized health/failure outcomes.
- [ ] Exercise the complete synthetic journey: email/password signup/login, CV upload/extraction, profile edit/confirmation, active CV switching, manual Indonesia/Global search, discovery/requirements/matching, score evidence, save/apply/ignore, filter-aware Excel/PDF export, original-only deletion, full CV deletion, and account deletion. Verify daily scheduling idempotency separately. Mark Google OAuth acceptance unverified unless an actual configured test OAuth flow is exercised; mocked configuration checks are not an OAuth login.
- [ ] Verify cross-user isolation with two users, private storage access, no personal data in general logs, and export ownership. Retain successful batch results when another source/provider item fails.
- [ ] Keep live provider testing optional. When explicitly enabled for the test environment, run:

```bat
cd apps\worker
set RUN_LIVE_AI_TESTS=1
uv run pytest tests/test_ai_contract_live_optional.py -q
set RUN_LIVE_AI_TESTS=
```

- [ ] Record skipped live checks as skipped, never passed. Do not claim the optional profile contract proves production matching, OAuth, or every source connector. Normal CI must remain quota-free.
- [ ] For each unavailable check, record the exact missing prerequisite, responsible runtime, and command needed to unblock it. Keep the corresponding completion checkbox open.

**Done when:** Mandatory SQL, browser, worker, and deployment checks have fresh successful evidence on the reviewed commit. Optional checks have explicit pass/skipped status. This task does not authorize production deployment, bulk historical recomputation, or testing against real user accounts.

**Review correction (2026-09-09):** The Playwright suite now contains explicit
checks for the missing-code OAuth callback branch, original-only retention,
Settings full deletion, account deletion, and completed export downloads. The
completed-export test has a 180-second test timeout for its 120-second worker
poll and checks included/excluded titles in both XLSX and PDF artifacts. It is
intentionally gated by `RUN_EXPORT_E2E=1`; without a running worker/storage
environment it remains skipped. The normal Playwright run is still blocked
before global setup by the missing `apps/web/.env`.

## Task 11: Reconcile completion records and deliver the final review

**Priority:** Required handoff accuracy.

**Modify:** This plan, `docs/VERIFICATION-2026-09-08.md`, and `docs/superpowers/plans/2026-09-06-critical-high-audit-remediation.md`.

**Preserve:** The pre-existing untracked `docs/PROJECT_ANALYSIS_REPORT.md`; cite corrections in the new evidence record instead of silently rewriting it.

- [ ] Match every row in the coverage matrix to a focused regression or explicit verification record. Attach task commit IDs and actual dates.
- [ ] Update the older remediation checklist with a dated correction for the Settings contract and unavailable integration gates; distinguish its historical results from the newly verified state.
- [ ] Inspect `git diff --stat`, `git diff --check`, `git status --short`, and task history. Ensure no unrelated report, private environment file, generated credential, or real CV fixture is staged.
- [ ] Re-run gates if code changed after Task 10; otherwise reuse that exact-commit evidence instead of needlessly repeating tests.
- [ ] Produce a final inventory with four states: implemented and verified; implemented but verification-blocked; still unimplemented; optional checks skipped. Do not mark the entire MVP complete while mandatory acceptance remains unverified.
- [ ] Commit only reviewed plan/evidence corrections as `docs: record verified audit remediation outcomes`.

**Done when:** All eight reported defect groups have a concrete disposition, every unfinished gate is either passed or honestly left open, and completion claims match the reviewed code and command output.

## 4. Per-task execution record

Fill a row only during implementation, using real command output. An em dash below means no execution evidence exists yet.

| Task | State | Commit | Focused red/green evidence | Broader checks | Remaining boundary |
|---|---|---|---|---|---|
| 1 | Complete | `9a7eba5` | Active 9Router docs and test-gate variable reconciled; `git diff --check` passed | Documentation diff reviewed | Gateway reachability still belongs to Task 10 |
| 2 | Complete | `352b9e5` | Ruff red baseline reproduced; focused worker tests, Ruff, mypy passed | 88 focused worker tests passed | None |
| 3 | Verification-blocked | `eaa7b27`, `ba6a88f`, `f489c37` | Settings full-mode fix plus success/failure component coverage; browser retention/full-delete journeys added | Web 153 tests, lint, and TypeScript passed | Disposable Supabase CV/RLS acceptance required |
| 4 | Verification-blocked | `54af1b7`, `8ffb0a9` | Existing RLS assertion corrected; privilege descriptions moved into pgTAP `ok(...)` assertions | SQL suite not executable without Supabase CLI | Disposable Supabase/Docker required |
| 5 | Complete | `b8600bb` | Four valid employer-domain regressions red then green; blocked-domain tests passed | 95 discovery/connector tests passed with Task 6 changes | None |
| 6 | Complete | `56dd816` | Generic Open Graph location regression red then green | 96 discovery/connector tests passed; Ruff/mypy passed | None |
| 7 | Complete | `f4ab3db`, `85de858` | Tail, exact 100,000-character boundary, complete router prompt, oversized-input, versioned-cache, legacy hash, and failure-preserving-cache regressions passed | 389 worker tests passed/1 skipped; Ruff/mypy passed | Historical saved matches require a new search to regenerate |
| 8 | Complete | `b68eab5` | Default extraction regression red then green; explicit false remains covered | 19 config/discovery tests passed | Provider availability remains an operational prerequisite |
| 9 | Complete | `19750d4` | Legacy/canonical alias and bounds regressions passed | 20 scheduler/export tests plus worker checks passed | None |
| 10 | Verification-blocked | `f489c37`, `2520ba7`, `ec2d38e` | Browser acceptance expanded for OAuth callback routing, CV retention/deletion, account deletion, and filtered completed downloads with timeout coverage | Worker 389 passed/1 skipped; web 153 passed; lint/type/build passed | SQL, Compose, and authenticated Playwright remain blocked; see `docs/VERIFICATION-2026-09-08.md` |
| 11 | Complete | `ee04062`, `ea7fdba` | Review findings, current local counts, and historical checklist correction recorded | `git diff --check`, web build, secret scan, and task-table review passed | SQL/Compose/Playwright remain open under Task 10 |
