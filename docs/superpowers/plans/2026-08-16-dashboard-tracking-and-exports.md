# Dashboard Tracking and Exports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the user-facing SaaS experience for ranked matches, detailed analysis, application tracking, bilingual UI, and filter-aware Excel/PDF downloads with clickable original job links.

**Architecture:** Next.js server components query only authenticated user-owned search runs/matches. Client components manage filters and status mutations. Export requests enqueue worker jobs that generate private XLSX/PDF artifacts and expose short-lived signed download URLs.

**Tech Stack:** Next.js 16, TypeScript, Tailwind CSS, next-intl, TanStack Table, Supabase, Python openpyxl/ReportLab, Vitest, Playwright, pytest.

---

## File structure locked by this plan

```text
supabase/migrations/202608160007_tracking_exports.sql
apps/web/app/dashboard/page.tsx
apps/web/app/jobs/[matchId]/page.tsx
apps/web/app/saved/page.tsx
apps/web/app/applications/page.tsx
apps/web/app/exports/page.tsx
apps/web/app/api/job-status/route.ts
apps/web/app/api/exports/route.ts
apps/web/components/jobs/{match-table,filters,score-badge}.tsx
apps/web/i18n/{request,routing}.ts
apps/web/messages/{id,en}.json
apps/worker/jobmatch_worker/exports/{models,excel,pdf,service}.py
```

### Task 1: Add job tracking and export schema

**Files:**
- Create: `supabase/migrations/202608160007_tracking_exports.sql`
- Test: `supabase/tests/tracking_exports.sql`

- [ ] **Step 1: Write failing schema assertions**

Assert `user_jobs` and `exports` missing before migration; expected FAIL.

- [ ] **Step 2: Implement tables and RLS**

```sql
create table public.user_jobs (
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references public.jobs(id) on delete cascade,
  status text not null check (status in ('new','saved','applied','ignored')),
  applied_at timestamptz,
  updated_at timestamptz not null default now(),
  primary key(user_id, job_id)
);

create table public.exports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  format text not null check (format in ('xlsx','pdf')),
  filter_json jsonb not null,
  status text not null default 'queued' check (status in ('queued','processing','completed','failed')),
  storage_path text,
  error_code text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.user_jobs enable row level security;
alter table public.exports enable row level security;
create policy user_jobs_owner_all on public.user_jobs for all using (auth.uid()=user_id) with check (auth.uid()=user_id);
create policy exports_owner_all on public.exports for all using (auth.uid()=user_id) with check (auth.uid()=user_id);

insert into storage.buckets(id,name,public) values('exports','exports',false)
on conflict(id) do update set public=false;
```
Add private storage policies matching first path segment to `auth.uid()` as done for CV storage.

- [ ] **Step 3: Verify and commit**

```bash
supabase db reset
supabase db test supabase/tests/tracking_exports.sql
git add supabase && git commit -m "feat: add application tracking and export schema"
```

### Task 2: Build ranked dashboard with bucket/filter logic

**Files:**
- Create: `apps/web/lib/jobs/buckets.ts`
- Create: `apps/web/lib/jobs/filter.ts`
- Create: `apps/web/components/jobs/match-table.tsx`
- Create: `apps/web/components/jobs/filters.tsx`
- Create: `apps/web/app/dashboard/page.tsx`
- Test: `apps/web/tests/job-filter.test.ts`

- [ ] **Step 1: Write failing bucket/filter tests**

```ts
import { bucketForScore } from "@/lib/jobs/buckets";

it("uses locked match buckets", () => {
  expect(bucketForScore(95)).toBe("best");
  expect(bucketForScore(85)).toBe("strong");
  expect(bucketForScore(75)).toBe("potential");
  expect(bucketForScore(69)).toBe("low");
});
```
Also test region/work mode/min score/status filters and default descending overall score.

- [ ] **Step 2: Implement bucket helper**

```ts
export type MatchBucket = "best" | "strong" | "potential" | "low";
export function bucketForScore(score: number): MatchBucket {
  if (score >= 90) return "best";
  if (score >= 80) return "strong";
  if (score >= 70) return "potential";
  return "low";
}
```

- [ ] **Step 3: Implement dashboard query and table**

Server-load the latest/current search run plus user-owned matches joined to jobs. Render summary cards (jobs found, best, strong, new today), filter bar, sortable columns, source/date/location/work mode, match badge, and actions `View Match`, `View Job`, `Save`. Original URLs open with `rel="noopener noreferrer"`.

- [ ] **Step 4: Test and commit**

```bash
pnpm --dir apps/web test -- job-filter.test.ts
pnpm --dir apps/web typecheck
git add apps/web && git commit -m "feat: add ranked match dashboard"
```

### Task 3: Build match-detail page and application status mutations

**Files:**
- Create: `apps/web/app/jobs/[matchId]/page.tsx`
- Create: `apps/web/app/api/job-status/route.ts`
- Create: `apps/web/app/saved/page.tsx`
- Create: `apps/web/app/applications/page.tsx`
- Test: `apps/web/tests/job-status.test.ts`

- [ ] **Step 1: Write failing status-transition tests**

Test allowed statuses `new/saved/applied/ignored`; setting `applied` assigns `applied_at`; moving from applied to saved clears `applied_at`; invalid status returns 400.

- [ ] **Step 2: Implement owner-scoped status upsert**

`POST /api/job-status` takes `{jobId,status}` and uses authenticated `user.id` server-side; never accepts a user id from the browser. Upsert `(user_id,job_id)` and set `applied_at=now()` only for `applied`.

- [ ] **Step 3: Implement match detail**

Render overall score, six dimensions, strengths, gaps, critical gaps, verdict, explanation, recommendations, and buttons `View Job`, `Save/Unsave`, `Mark Applied`, `Ignore`. Show critical gaps above ordinary gaps. Never render AI output as raw HTML.

- [ ] **Step 4: Test and commit**

```bash
pnpm --dir apps/web test -- job-status.test.ts
pnpm --dir apps/web typecheck
git add apps/web && git commit -m "feat: add match detail and application tracking"
```

### Task 4: Add Bahasa Indonesia and English UI/messages

**Files:**
- Create: `apps/web/i18n/routing.ts`
- Create: `apps/web/i18n/request.ts`
- Create: `apps/web/messages/id.json`
- Create: `apps/web/messages/en.json`
- Modify: `apps/web/app/layout.tsx`
- Test: `apps/web/tests/i18n.test.ts`

- [ ] **Step 1: Write failing key-parity test**

Load both JSON files recursively and assert identical translation-key sets.

- [ ] **Step 2: Add next-intl and locale persistence**

Run:
```bash
pnpm --dir apps/web add next-intl
```
Use only `id` and `en`; default to `id`; persist the selected locale to `profiles.locale`; pass locale to export requests so AI explanations already stored in one language are not silently mistranslated—only UI labels/report framing are localized unless a localized explanation was generated.

- [ ] **Step 3: Translate MVP UI key set**

Both message files must contain keys for navigation, auth, CV, search form, processing states, four match buckets, six score dimensions, strengths/gaps/critical gaps, tracking statuses, export labels, settings, errors, and empty states.

- [ ] **Step 4: Test and commit**

```bash
pnpm --dir apps/web test -- i18n.test.ts
pnpm --dir apps/web typecheck
git add apps/web && git commit -m "feat: add Indonesian and English UI"
```

### Task 5: Implement filter-aware Excel export

**Files:**
- Create: `apps/worker/jobmatch_worker/exports/models.py`
- Create: `apps/worker/jobmatch_worker/exports/excel.py`
- Test: `apps/worker/tests/test_excel_export.py`

- [ ] **Step 1: Add dependencies and failing workbook test**

Run:
```bash
cd apps/worker && uv add openpyxl
```
Test generated workbook has sheets exactly `Job Matches`, `Candidate Profile`, `Search Criteria`; filtered rows only; `Job URL` cells are hyperlinks; score columns are numeric; frozen header and autofilter exist.

- [ ] **Step 2: Implement workbook writer**

`Job Matches` columns:
```text
Job Title, Company, Location, Region, Work Mode, Employment Type,
Salary Min, Salary Max, Currency, Published Date, Overall Match,
Skills, Experience, Education, Location Score, Seniority, Language,
Verdict, Strengths, Gaps, Critical Gaps, AI Recommendation, Source, Job URL
```
Serialize array fields with newline separators. Do not include raw CV text or private storage paths.

- [ ] **Step 3: Run test and commit**

```bash
cd apps/worker && uv run pytest tests/test_excel_export.py -q
git add apps/worker && git commit -m "feat: generate filter-aware Excel reports"
```

### Task 6: Implement PDF report export

**Files:**
- Create: `apps/worker/jobmatch_worker/exports/pdf.py`
- Test: `apps/worker/tests/test_pdf_export.py`

- [ ] **Step 1: Add ReportLab and failing PDF test**

```bash
cd apps/worker && uv add reportlab
```
Test that generated PDF bytes start `%PDF-`, contain candidate/search summary and top match job titles when parsed by a PDF text reader, and include link annotations for original job URLs.

- [ ] **Step 2: Implement bounded report layout**

Use ReportLab Platypus. Sections: title/date, candidate summary, search criteria, aggregate stats, top matches table, then per-job details for exported rows. For large result sets, keep per-job details concise and let Excel carry exhaustive tabular detail. Add clickable links with ReportLab link markup; escape user/job text before markup.

- [ ] **Step 3: Run test and commit**

```bash
cd apps/worker && uv run pytest tests/test_pdf_export.py -q
git add apps/worker && git commit -m "feat: generate clickable PDF match reports"
```

### Task 7: Queue exports and provide signed downloads

**Files:**
- Create: `apps/worker/jobmatch_worker/exports/service.py`
- Create: `apps/web/app/api/exports/route.ts`
- Create: `apps/web/app/exports/page.tsx`
- Test: `apps/web/tests/export-request.test.ts`
- Test: `apps/worker/tests/test_export_service.py`

- [ ] **Step 1: Write failing filter contract tests**

Allowed export scopes: `all`, `current_filters`, `best_and_strong`. Current filters must be a validated object containing only region/work mode/min score/status/date range; reject arbitrary SQL-like fields.

- [ ] **Step 2: Implement export request route**

Create `exports` row, enqueue `generate_export:<export_id>`, return 202. Worker re-runs the validated filter against user-owned match data server-side, generates XLSX/PDF, uploads to private path `${user_id}/${export_id}/report.ext`, sets completed status.

- [ ] **Step 3: Implement download route/page**

When completed, server creates a short-lived signed storage URL only after verifying `exports.user_id == auth.uid()`. Never persist signed URLs in the database.

- [ ] **Step 4: Run tests and commit**

```bash
pnpm --dir apps/web test -- export-request.test.ts
cd apps/worker && uv run pytest tests/test_export_service.py -q
git add apps && git commit -m "feat: add private queued report downloads"
```

### Task 8: Add core Playwright journey through dashboard/export

**Files:**
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/e2e/dashboard.spec.ts`

- [ ] **Step 1: Install Playwright and seed deterministic test data**

```bash
pnpm --dir apps/web add -D @playwright/test
pnpm --dir apps/web exec playwright install chromium
```
Seed one authenticated test user, one active CV/profile, one completed run with best/strong/potential/low matches.

- [ ] **Step 2: Write E2E test**

Test login, dashboard bucket counts, filter `>=80`, open match detail, mark saved then applied, request Excel export, and verify export row becomes queued. External `View Job` link should be asserted by href, not actually navigated in CI.

- [ ] **Step 3: Run and commit**

```bash
pnpm --dir apps/web exec playwright test e2e/dashboard.spec.ts
git add apps/web && git commit -m "test: cover dashboard tracking and export journey"
```
Expected: PASS.

## Plan 5 acceptance checkpoint

A logged-in user can browse all match buckets, filter/sort results, inspect full match explanations, Save/Apply/Ignore jobs, switch Bahasa Indonesia/English, and request filter-aware XLSX/PDF exports. Download links are private and short-lived; original job URLs are clickable in the UI and generated files.
