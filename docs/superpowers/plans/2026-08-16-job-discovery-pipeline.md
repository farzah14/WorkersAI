# Job Discovery Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user confirm an AI-assisted search profile, trigger Indonesia or Global discovery, and persist normalized deduplicated jobs from multiple independent sources without requiring every source to succeed.

**Architecture:** Next.js writes a `job_search_run` and enqueues discovery work. The Python worker fans out to source connectors (Brave Search, Greenhouse, Lever, permitted career-page fetcher), normalizes results into a shared contract, canonicalizes URLs, deduplicates before expensive AI work, and records per-source outcomes.

**Tech Stack:** PostgreSQL, Next.js, Pydantic, HTTPX, BeautifulSoup/lxml, `urllib.robotparser`, RapidFuzz, Brave Search API, Greenhouse Job Board API, Lever Postings API, pytest/Vitest.

---

## File structure locked by this plan

```text
supabase/migrations/202608160005_job_discovery.sql
apps/web/app/find-jobs/page.tsx
apps/web/app/api/search-runs/route.ts
apps/worker/jobmatch_worker/jobs/
├── models.py
├── query.py
├── normalize.py
├── canonicalize.py
├── dedupe.py
└── connectors/{base,brave,greenhouse,lever,career_page}.py
apps/worker/jobmatch_worker/handlers/discovery.py
```

### Task 1: Add search profile and job catalog schema

**Files:**
- Create: `supabase/migrations/202608160005_job_discovery.sql`
- Test: `supabase/tests/job_discovery.sql`

- [ ] **Step 1: Write failing table assertions**

Assert existence of `search_profiles`, `job_search_runs`, `job_sources`, `jobs`, and `job_search_run_jobs` before migration; expected FAIL.

- [ ] **Step 2: Implement schema**

```sql
create table public.search_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  candidate_profile_id uuid not null references public.candidate_profiles(id) on delete cascade,
  region text not null check (region in ('indonesia','global')),
  target_roles text[] not null,
  locations text[] not null default '{}',
  work_modes text[] not null default '{}',
  employment_types text[] not null default '{full-time}',
  min_salary numeric,
  salary_currency text,
  excluded_keywords text[] not null default '{}',
  daily_enabled boolean not null default false,
  is_current boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.job_search_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  search_profile_id uuid not null references public.search_profiles(id),
  candidate_profile_id uuid not null references public.candidate_profiles(id),
  trigger text not null check (trigger in ('manual','daily')),
  status text not null default 'queued' check (status in ('queued','processing','completed','partial','failed')),
  discovered_count integer not null default 0,
  normalized_count integer not null default 0,
  duplicate_count integer not null default 0,
  failed_count integer not null default 0,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.job_sources (
  id uuid primary key default gen_random_uuid(),
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  source_type text not null,
  source_key text not null,
  status text not null check (status in ('queued','success','failed','skipped')),
  result_count integer not null default 0,
  error_code text,
  created_at timestamptz not null default now()
);

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null unique,
  title text not null,
  company text not null,
  location text,
  country text,
  region text not null default 'unknown' check (region in ('indonesia','global','unknown')),
  work_mode text,
  employment_type text,
  salary_min numeric,
  salary_max numeric,
  salary_currency text,
  description text not null,
  source_name text not null,
  original_url text not null,
  canonical_url text not null,
  published_at timestamptz,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  last_checked_at timestamptz not null default now(),
  status text not null default 'active' check (status in ('active','expired','unavailable','unknown'))
);

create table public.job_search_run_jobs (
  search_run_id uuid not null references public.job_search_runs(id) on delete cascade,
  job_id uuid not null references public.jobs(id) on delete restrict,
  primary key(search_run_id, job_id)
);

grant select on public.jobs to authenticated;
revoke all on public.work_items from anon, authenticated;
```
Canonical jobs are shared records, so `job_search_run_jobs.job_id` and `job_provenance.job_id` use `ON DELETE RESTRICT`; deleting a search run cascades its source, join, and provenance rows without deleting the shared job.
Enable RLS on user-owned tables and owner policies on `search_profiles`/`job_search_runs`/`job_sources`; grant authenticated users `SELECT` on the non-PII global `jobs` catalog; keep `job_matches`, profiles, search runs, CVs, exports, and tracking rows protected by owner RLS. Explicitly revoke browser access to `work_items` and operational `ai_requests` tables.

- [ ] **Step 3: Verify DB reset and tests**

Run `supabase db reset` and the TAP-aware test wrapper; expected exit code 0 and PASS.

```bash
supabase db reset
scripts/test-db.cmd supabase/tests/job_discovery.sql
```

`scripts/test-db.cmd` runs `supabase db test <file>` and exits nonzero when pgTAP emits `not ok` or `Failed` lines, so a failing TAP stream cannot silently pass with exit code 0.

- [ ] **Step 4: Commit**

```bash
git add supabase && git commit -m "feat: add search runs and job catalog schema"
```

### Task 2: Implement search profile UI and run trigger

**Files:**
- Create: `apps/web/lib/search/schema.ts`
- Create: `apps/web/app/find-jobs/page.tsx`
- Create: `apps/web/app/api/search-runs/route.ts`
- Test: `apps/web/tests/search-profile.test.ts`

- [ ] **Step 1: Write failing validation tests**

Test `region` only accepts `indonesia|global`, at least one target role is required, work mode only accepts `remote|hybrid|on-site`, and minimum salary cannot be negative.

- [ ] **Step 2: Implement Zod schema and form**

The page pre-populates target roles/seniority-derived preferences from the confirmed candidate profile, displays explicit `[Indonesia] [Global]` toggle, locations, work modes, employment types, optional salary, excluded keywords, and daily-discovery toggle.

- [ ] **Step 3: Implement `POST /api/search-runs`**

In one server-side transaction using the server-only Supabase `service_role` client: create a new current `search_profile`, mark prior current profiles false, create `job_search_runs(trigger='manual')`, enqueue `discover_jobs:<run_id>`, and return 202 with run id. Never expose the service-role key to the browser. Reject requests lacking a confirmed active candidate profile with HTTP 409.

- [ ] **Step 4: Test and commit**

```bash
pnpm --dir apps/web test -- search-profile.test.ts
pnpm --dir apps/web typecheck
git add apps/web && git commit -m "feat: add editable job search profile"
```

### Task 3: Define normalized job and query-builder contracts

Before Step 1 run:
```bash
cd apps/worker && uv add beautifulsoup4 lxml rapidfuzz
```

**Files:**
- Create: `apps/worker/jobmatch_worker/jobs/models.py`
- Create: `apps/worker/jobmatch_worker/jobs/query.py`
- Test: `apps/worker/tests/test_job_models.py`
- Test: `apps/worker/tests/test_job_query.py`

- [ ] **Step 1: Write failing model/query tests**

```python
def test_indonesia_query_mentions_country_and_role():
    q = build_queries(region="indonesia", roles=["Data Engineer"], locations=["Jakarta"])
    assert any("Data Engineer" in x and "Jakarta" in x and "Indonesia" in x for x in q)

def test_global_query_supports_remote():
    q = build_queries(region="global", roles=["Data Engineer"], locations=[], remote=True)
    assert any("remote" in x.lower() for x in q)
```

- [ ] **Step 2: Implement `DiscoveredJob` Pydantic model**

Fields: source_name/source_key, title, company, location/country/work_mode/employment_type, salary bounds/currency optional, description, original_url, published_at optional. Require non-empty title/company/description/original URL.

- [ ] **Step 3: Implement bounded query generation**

Generate at most 6 search queries per run: top 3 target roles × at most 2 location variants. Add `Indonesia` for Indonesia mode; add `remote` when requested. Append excluded keywords as negative quoted terms only when the selected search provider supports it.

- [ ] **Step 4: Run tests and commit**

```bash
cd apps/worker && uv run pytest tests/test_job_models.py tests/test_job_query.py -q
git add apps/worker && git commit -m "feat: define job discovery contracts"
```

### Task 4: Implement source connectors with isolation

**Files:**
- Create: `apps/worker/jobmatch_worker/jobs/connectors/base.py`
- Create: `brave.py`, `greenhouse.py`, `lever.py`, `career_page.py`
- Test: `apps/worker/tests/test_job_connectors.py`

- [ ] **Step 1: Write mocked connector tests**

Each connector must return `list[DiscoveredJob]` or `list[DiscoveryCandidateUrl]` and raise `SourceUnavailable` for retryable source failures. Tests must prove a 500 from one connector does not prevent another connector from returning results.

- [ ] **Step 2: Implement Brave Search connector**

Call the official Brave Search API with one query at a time, `count<=20`, safe search appropriate for normal web search, and map result title/URL/snippet to candidate URLs. Keep API key server-side. Do not treat snippets as complete job descriptions.

- [ ] **Step 3: Implement Greenhouse and Lever connectors**

Greenhouse: fetch public board JSON using configured/discovered board token and `content=true`; map published jobs to `DiscoveredJob`.

Lever: fetch published postings JSON for configured/discovered site name; map hosted URL, text description, location/team/commitment fields.

- [ ] **Step 4: Implement permitted career-page fetcher**

Before fetching a discovered HTML page, check scheme is HTTPS, resolve DNS and reject private/loopback/link-local IPs (SSRF protection), apply `urllib.robotparser` policy, cap response at 2 MiB, allow only `text/html`, timeout at 10 seconds, and strip scripts/styles/forms before extracting visible job text. Never execute JavaScript or submit forms in MVP.

- [ ] **Step 5: Run tests and commit**

```bash
cd apps/worker && uv run pytest tests/test_job_connectors.py -q
git add apps/worker && git commit -m "feat: add isolated job discovery connectors"
```

### Task 5: Normalize, canonicalize, and deduplicate before AI

**Files:**
- Create: `apps/worker/jobmatch_worker/jobs/canonicalize.py`
- Create: `apps/worker/jobmatch_worker/jobs/normalize.py`
- Create: `apps/worker/jobmatch_worker/jobs/dedupe.py`
- Test: `apps/worker/tests/test_job_dedupe.py`

- [ ] **Step 1: Write failing canonicalization/dedup tests**

Test stripping tracking params (`utm_*`, `gh_src`, common referral params), lowercasing hostname, preserving semantic query params, and treating same normalized company/title/location + canonical URL as same fingerprint.

- [ ] **Step 2: Implement canonical URL function**

Use `urllib.parse`; only allow `https`; sort retained query parameters; remove fragments; strip known tracking keys; normalize trailing slash. Reject URLs with embedded credentials.

- [ ] **Step 3: Implement fingerprint and fuzzy secondary check**

Primary fingerprint: SHA-256 of normalized company, title, location, canonical URL. Secondary duplicate check uses RapidFuzz token-set ratio >= 95 for same normalized company and location when canonical URLs differ.

- [ ] **Step 4: Persist via upsert**

Upsert `jobs` on fingerprint, update `last_seen_at`, link to `job_search_run_jobs`, increment duplicate count when an existing row is reused. Do this before requirement extraction/matching is enqueued.

- [ ] **Step 5: Run tests and commit**

```bash
cd apps/worker && uv run pytest tests/test_job_dedupe.py -q
git add apps/worker && git commit -m "feat: normalize and deduplicate discovered jobs"
```

### Task 6: Orchestrate a partial-success search run

**Files:**
- Create: `apps/worker/jobmatch_worker/handlers/discovery.py`
- Test: `apps/worker/tests/test_discovery_handler.py`

- [ ] **Step 1: Write failing partial-success test**

Use three fake connectors: one returns 3 jobs, one raises `SourceUnavailable`, one returns 2 jobs including a duplicate. Assert run becomes `partial`, normalized count is 4, duplicate count is 1, failed source is recorded, and downstream work is still enqueued for 4 jobs.

- [ ] **Step 2: Implement orchestration**

Set run `processing`; execute source connectors independently with bounded concurrency 4; persist source status; normalize/dedupe each result; enqueue `extract_job_requirements:<job_id>:<description_hash>` only for jobs lacking cached requirements; set run `completed` when all source attempts succeed, `partial` when at least one succeeds and one fails, and `failed` only when no source yields usable jobs.

- [ ] **Step 3: Run full worker tests**

```bash
cd apps/worker && uv run pytest -q
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/worker && git commit -m "feat: orchestrate resilient job discovery runs"
```

## Plan 3 acceptance checkpoint

Manual smoke with a confirmed profile: choose Indonesia, trigger `Find Jobs Now`, observe source isolation, normalized rows and canonical links. Repeat with Global. Verify duplicates collapse before any AI requirement extraction is enqueued. A failing connector must produce `partial`, not fail the whole run when another connector succeeds.
