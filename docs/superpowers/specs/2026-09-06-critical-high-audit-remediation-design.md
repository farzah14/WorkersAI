# Critical and High Audit Remediation Design

**Date:** 2026-09-06
**Audit source:** `/home/farzah/Downloads/AUDIT-RESULTS-2026-09-06.md`
**Baseline commit:** `e58a023`

## Goal

Resolve every critical and high-severity defect verified by the 2026-09-06 repository audit without changing the approved MVP scope or locked architecture. Remediation proceeds one defect at a time, with a focused regression test, the minimum implementation, affected-suite verification, and a coherent commit for each defect.

## Scope

This remediation covers the ten critical and high findings from the audit:

1. Daily scheduler rows do not contain the fields used to enqueue discovery work.
2. Authenticated callers can increment another user's API quota.
3. Failed CV creation can leave an unreferenced private storage object, and account deletion ignores storage-path enumeration failures.
4. Deleting an original CV also deletes the structured candidate profile.
5. Email/password signup signs the new user out instead of continuing to the dashboard.
6. Profile confirmation and active-CV selection are not atomic.
7. Discovery truncates distinct jobs to two and reports the remainder as duplicates.
8. Production discovery does not wire the Greenhouse and Lever connectors and loses duplicate-source provenance.
9. The web and worker export-filter contracts disagree, and the dashboard cannot request an export.
10. Matching runs can remain in `PROCESSING` after terminal AI-provider unavailability.

The audit's lower-priority findings are explicitly excluded from this remediation cycle. They remain eligible for a later design and plan.

## Constraints

- Preserve Next.js 16, Supabase, PostgreSQL, and the Python asyncio worker architecture.
- Apply database changes through new append-only migrations.
- Derive user ownership from the authenticated server context; do not weaken RLS or accept browser-provided ownership claims.
- Keep original CV objects private and remove newly uploaded objects when later creation steps fail.
- Keep discovery connectors isolated so one failed source can produce a `PARTIAL` run instead of discarding successful sources.
- Preserve deterministic match scores and the provider-neutral AI router.
- Keep Bahasa Indonesia and English message keys synchronized for new export UI copy.
- Do not require live AI-provider calls in ordinary tests.

## Remediation sequence

The sequence is risk-first, as approved by the user. Each numbered item is completed and verified before the next begins.

### 1. Scheduler return contract

Change the run insertion query to return the run identifier and the three identifiers required by the queued discovery payload. Replace the test fake that invents those fields with a result shaped exactly like PostgreSQL's `RETURNING` result. The regression test must fail with the current query/result mismatch and pass only when the production result contract supplies every payload field.

### 2. Quota ownership enforcement

Add a migration that replaces `increment_api_usage` with an authenticated-ownership check. An authenticated caller may increment only `auth.uid()`; the service role may perform server-side increments where required. SQL/RLS tests must demonstrate same-user success, cross-user denial, and service-role behavior. Existing rate-limit callers retain the current RPC name and parameter contract unless the test environment proves a safer compatible signature is required.

### 3. CV and account-deletion storage safety

Treat storage upload plus database/queue creation as a compensating transaction: after an upload succeeds, any later failure attempts to remove that exact object before returning the sanitized API error. The cleanup path must not conceal the original failure, but its failure must be observable without logging CV contents or signed URLs.

Account deletion must stop before deleting the account when CV/export path enumeration fails. It must distinguish an empty successful result from an enumeration error, so the system cannot report deletion while private objects may be undiscovered.

### 4. Original-file deletion without profile deletion

Separate two operations that currently share destructive behavior:

- delete only the retained original object and clear its storage reference while preserving the CV record and structured candidate profile;
- delete the complete CV record and its dependent profile when the user explicitly requests full CV deletion.

The profile UI must use the original-only operation for the retention control. Database and route tests must prove the confirmed profile remains available after original-file deletion.

### 5. Authenticated signup continuation

Remove the explicit sign-out after successful email/password registration. When Supabase returns an authenticated session under the approved no-verification configuration, redirect directly to the dashboard. Preserve existing handling for duplicate accounts and provider responses that do not include a session. Contract tests must cover both session-present and session-absent outcomes without depending on a live Supabase project.

### 6. Atomic profile confirmation and activation

Move profile persistence and active-CV transition behind one server-authorized PostgreSQL function invoked by the web server. The transaction must confirm the submitted profile, deactivate the prior active CV when necessary, activate the selected CV, and update current search-profile linkage as one unit. Any constraint or activation failure rolls back every change. The migration must enforce authenticated ownership and keep the existing exactly-one-active-CV database invariant.

### 7. Discovery result completeness

Remove the two-job run cap. Retain the existing bounded per-source and career-candidate safety limits. Duplicate counts must contain only actual in-run or database duplicates; distinct jobs may not be reclassified as duplicates because of an arbitrary output cap. The Plan 3 acceptance-shaped test must yield four normalized jobs from five inputs containing one real duplicate.

**Superseded 2026-09-09:** The user-approved MVP rule in
`2026-09-09-five-job-search-limit-design.md` now limits each search run to five
distinct jobs after normalization and deduplication. Omitted valid jobs still
must not increase `duplicate_count`.

### 8. Hybrid sources and provenance

Build production sources from Tavily, Greenhouse, and Lever using their existing connector interfaces and configuration. A missing or invalid source configuration becomes an isolated source failure rather than disabling successful sources.

Provenance persistence must receive all normalized discoveries plus the deduplicated retained set. When multiple source discoveries resolve to one canonical job, persist every source association against that canonical record. Tests must cover isolated source failure, ATS query de-duplication, and multiple-source provenance for one canonical job.

### 9. Export request contract and controls

Define one canonical export-filter shape shared conceptually by the web request validator and worker Pydantic model. Multi-select dimensions use arrays; single-valued dimensions remain scalar only where both runtimes agree. The web route serializes the exact worker-compatible payload.

Add accessible Excel and PDF request controls to the exports experience. Requests use the current dashboard filters, display pending/success/error states, and refresh the export list after acceptance. Both locales receive matching message keys. Route, component, and worker contract tests must prove that a web-shaped request validates and reaches the queue unchanged.

### 10. Terminal matching-run accounting

Unify terminal failure accounting so every requirement-extraction or matching work item decrements/completes its search-run stage even when no AI provider is available. A run becomes `FAILED` when no useful result exists, or `PARTIAL` when other work produced useful results. Work-item failure and run-status transition occur in the same database transaction. Regression tests must prove no terminal provider-unavailable path leaves the run in `PROCESSING`.

## Error handling and observability

- Preserve sanitized error categories instead of provider bodies, credentials, CV text, or storage URLs.
- Keep retries bounded and use them only for retryable transport/provider failures.
- Compensating storage deletion is attempted only for the exact object created by the failed request.
- Source-level discovery failures remain isolated and are included in final run accounting.
- Database authorization failures are terminal and never trigger provider fallback.

## Testing strategy

Every remediation uses red-green-refactor:

1. Add a focused regression test that reaches the audited production seam.
2. Run it and confirm the expected defect-specific failure.
3. Make the minimum production change.
4. Run the focused test until it passes.
5. Run the affected web, worker, or SQL/RLS suite.
6. Run lint and type checks for the affected runtime.
7. Run `git diff --check` and commit the coherent fix.

After all ten fixes, run the complete available verification matrix:

- web unit tests, lint, TypeScript checks, and production build;
- worker pytest, Ruff, and mypy;
- Supabase SQL/RLS tests when the local Supabase runtime is available;
- Docker Compose validation when Docker is available;
- authenticated Playwright E2E when its seeded local Supabase environment is available;
- tracked-file secret-pattern scan and `git diff --check`.

Unavailable external verification is reported as an explicit boundary, never as a pass.

## Completion criteria

- All ten audit findings have a defect-specific regression test and verified fix.
- Each fix is committed separately in the approved sequence.
- All locally available affected and full suites pass with fresh output.
- New migrations are append-only and include ownership/RLS verification.
- No raw CV text, credentials, signed URLs, or secrets appear in source, fixtures, or logs.
- The implementation remains consistent with the approved MVP design and six-plan architecture.
