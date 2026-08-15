# Daily Discovery and Production Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MVP production-operable with daily discovery, idempotent recovery, rate limits, privacy/deletion workflows, observability, job freshness checks, Docker/VPS deployment, and an acceptance-level end-to-end suite.

**Architecture:** A scheduler process on the same VPS enqueues daily runs using PostgreSQL as the durable coordination layer. Web and worker enforce defense-in-depth authorization and quotas. Structured metrics avoid raw CV content. Docker Compose runs only the worker and scheduler; Vercel, Supabase, NVIDIA NIM, OpenRouter, and Ollama Cloud remain managed external services.

**Tech Stack:** Python asyncio, PostgreSQL advisory/row locks, Next.js, Supabase, Docker Compose, HTTPX cloud AI adapters, pytest, Playwright, structured JSON logs.

---

## File structure locked by this plan

```text
supabase/migrations/202608160006_hardening.sql
apps/worker/jobmatch_worker/scheduler.py
apps/worker/jobmatch_worker/metrics.py
apps/worker/jobmatch_worker/jobs/freshness.py
apps/web/lib/rate-limit.ts
apps/web/app/api/account/delete/route.ts
apps/web/app/settings/page.tsx
infra/worker/Dockerfile
infra/worker/entrypoint.sh
compose.production.yml
scripts/production-smoke.sh
apps/web/e2e/mvp.spec.ts
```

### Task 1: Add idempotency, quotas, and operational metadata

**Files:**
- Create: `supabase/migrations/202608160006_hardening.sql`
- Test: `supabase/tests/hardening.sql`

- [ ] **Step 1: Write failing assertions**

Assert existence of `api_usage_windows` and a unique daily-run key after migration; expected FAIL before implementation.

- [ ] **Step 2: Implement schema changes**

```sql
create table public.api_usage_windows (
  user_id uuid not null references auth.users(id) on delete cascade,
  action text not null,
  window_start timestamptz not null,
  count integer not null default 0,
  primary key(user_id, action, window_start)
);

alter table public.job_search_runs
add column idempotency_key text;
create unique index job_search_runs_idempotency_key_unique
on public.job_search_runs(idempotency_key)
where idempotency_key is not null;

create index work_items_ready_idx
on public.work_items(status, available_at, created_at)
where status='queued';
```

- [ ] **Step 3: Verify and commit**

```bash
supabase db reset
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/hardening.sql
git add supabase && git commit -m "feat: add production idempotency and quota schema"
```

### Task 2: Implement daily scheduler with one run per profile/day

**Files:**
- Create: `apps/worker/jobmatch_worker/scheduler.py`
- Test: `apps/worker/tests/test_scheduler.py`

- [ ] **Step 1: Write failing scheduler test**

Given two daily-enabled current profiles, scheduler creates exactly two runs; a second invocation for the same UTC date creates zero additional runs. Profiles without confirmed active CV are skipped with reason metadata.

- [ ] **Step 2: Implement deterministic daily idempotency key**

Use:
```python
def daily_key(user_id: str, search_profile_id: str, day: date) -> str:
    return f"daily:{user_id}:{search_profile_id}:{day.isoformat()}"
```
Insert run with `ON CONFLICT(idempotency_key) DO NOTHING`, enqueue discovery only when row was inserted.

- [ ] **Step 3: Use one scheduler process in Compose**

Scheduler wakes every 15 minutes and selects daily-enabled profiles whose local-day run is absent. MVP uses user locale only for UI; scheduling uses a configurable `DAILY_DISCOVERY_HOUR_ASIA_JAKARTA=7` and converts to UTC. Do not create per-user arbitrary time zones in MVP.

- [ ] **Step 4: Test and commit**

```bash
cd apps/worker && uv run pytest tests/test_scheduler.py -q
git add apps/worker && git commit -m "feat: schedule idempotent daily job discovery"
```

### Task 3: Add request quotas and abuse protection

**Files:**
- Create: `apps/web/lib/rate-limit.ts`
- Modify: `apps/web/app/api/cvs/route.ts`
- Modify: `apps/web/app/api/search-runs/route.ts`
- Modify: `apps/web/app/api/exports/route.ts`
- Test: `apps/web/tests/rate-limit.test.ts`

- [ ] **Step 1: Write failing quota tests**

Lock initial MVP limits as configuration defaults, not product promises: upload 10/day/user, manual search 10/day/user, export 20/day/user. Tests assert action is allowed before limit and returns retry-after metadata after limit.

- [ ] **Step 2: Implement atomic Postgres quota increment**

Create a SQL RPC/function that buckets by UTC day and atomically inserts/increments `api_usage_windows`, returning the new count. Web calls it only after authentication; IP-level edge rate limiting may be added later but user-level quotas are required now.

- [ ] **Step 3: Apply to costly endpoints**

After auth and before performing storage/queue work, enforce action limit; return HTTP 429 with `Retry-After` seconds until next UTC day. Do not charge quota for validation failures that happen before any external/worker work.

- [ ] **Step 4: Test and commit**

```bash
pnpm --dir apps/web test -- rate-limit.test.ts
pnpm --dir apps/web typecheck
git add apps/web supabase && git commit -m "feat: rate limit costly user operations"
```

### Task 4: Add job freshness and dead-link handling

**Files:**
- Create: `apps/worker/jobmatch_worker/jobs/freshness.py`
- Test: `apps/worker/tests/test_job_freshness.py`

- [ ] **Step 1: Write failing status mapping tests**

Assert 200/valid page -> active, 404/410 -> unavailable, expired markers from known ATS payloads -> expired, network timeout -> unknown and must not delete the job.

- [ ] **Step 2: Implement bounded recheck**

Before presenting jobs older than 7 days in a new daily run, recheck canonical URL or source API when available. Use HEAD only when source supports it; otherwise small GET. Do not follow more than 3 redirects; retain last known data even when unavailable.

- [ ] **Step 3: Exclude unavailable jobs from new recommendations**

Historical match remains visible but dashboard marks status unavailable/expired. New daily runs do not enqueue matching for unavailable/expired jobs unless rediscovered as active.

- [ ] **Step 4: Test and commit**

```bash
cd apps/worker && uv run pytest tests/test_job_freshness.py -q
git add apps/worker && git commit -m "feat: recheck job freshness and dead links"
```

### Task 5: Implement user privacy deletion workflows

**Files:**
- Create: `apps/web/app/api/account/delete/route.ts`
- Create: `apps/web/app/settings/page.tsx`
- Test: `apps/web/tests/account-delete.test.ts`

- [ ] **Step 1: Write failing ownership/deletion tests**

Test original CV delete removes private object but retains structured profile when explicitly requested; account delete removes CV objects and export objects before deleting the auth user; one user cannot request another user's object deletion.

- [ ] **Step 2: Implement CV original-file deletion**

Server verifies owner, deletes exact `storage_path`, sets `storage_path=null` and `retain_original=false`; candidate profile remains. If storage object is already absent, treat delete as idempotent success.

- [ ] **Step 3: Implement account deletion**

Require recent authenticated session and explicit confirmation token `DELETE`. Enumerate owner CV/export storage paths server-side, delete objects, delete auth user using server-only admin credential; Postgres cascades user-owned rows. Never accept target user id from request body.

- [ ] **Step 4: Test and commit**

```bash
pnpm --dir apps/web test -- account-delete.test.ts
pnpm --dir apps/web typecheck
git add apps/web && git commit -m "feat: add privacy deletion controls"
```

### Task 6: Add structured observability without raw CV logging

**Files:**
- Create: `apps/worker/jobmatch_worker/metrics.py`
- Modify: `apps/worker/jobmatch_worker/main.py`
- Test: `apps/worker/tests/test_logging_privacy.py`

- [ ] **Step 1: Write failing redaction test**

Provide payload containing `extracted_text`, email, and storage path; assert serialized operational log contains IDs/counts/status but not extracted CV text or signed URLs.

- [ ] **Step 2: Implement structured event logger**

Emit JSON events for queue claim/complete/fail, search-run counters, connector status, AI provider attempt/fallback/latency, matches success/fail, export completion, scheduler-created runs. Allowed identifiers: run/job/work item UUIDs; user id should be hashed in logs unless required for incident response.

- [ ] **Step 3: Add run metrics query**

Create a worker/admin query that returns discovered/duplicate/normalized/matched/failed counts and AI calls/fallback counts for a run from database metadata. Do not query raw CV text.

- [ ] **Step 4: Test and commit**

```bash
cd apps/worker && uv run pytest tests/test_logging_privacy.py -q
git add apps/worker && git commit -m "feat: add privacy-safe operational observability"
```

### Task 7: Containerize worker and scheduler on one VPS

**Files:**
- Create: `infra/worker/Dockerfile`
- Create: `compose.production.yml`
- Create: `scripts/production-smoke.sh`

- [ ] **Step 1: Create worker image**

`infra/worker/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY apps/worker/pyproject.toml apps/worker/uv.lock ./
RUN uv sync --frozen --no-dev
COPY apps/worker/jobmatch_worker ./jobmatch_worker
CMD ["uv", "run", "python", "-m", "jobmatch_worker.main"]
```

- [ ] **Step 2: Create production Compose with cloud AI configuration**

Create `compose.production.yml`:
```yaml
services:
  worker:
    build:
      context: .
      dockerfile: infra/worker/Dockerfile
    env_file: .env.production
    restart: unless-stopped
  scheduler:
    build:
      context: .
      dockerfile: infra/worker/Dockerfile
    env_file: .env.production
    command: ["uv","run","python","-m","jobmatch_worker.scheduler"]
    restart: unless-stopped
```

`.env.production` is created only on the server and is never committed. It contains database/storage credentials plus `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`, `OLLAMA_API_KEY`, configured model identifiers, and `OLLAMA_BASE_URL=https://ollama.com/api`. Do not add an Ollama service, model volume, model pull, GPU runtime, or port `11434`.

- [ ] **Step 3: Add smoke script**

`scripts/production-smoke.sh` must `set -euo pipefail`, verify worker and scheduler containers are running, execute one database connectivity query, and print only non-secret status. Live AI provider health checks are opt-in because they can consume quota; ordinary smoke validation must not print keys or provider response bodies.

- [ ] **Step 4: Build and test locally**

```bash
docker compose -f compose.production.yml build
docker compose -f compose.production.yml config
```
Expected: both commands exit 0 and `docker compose config` contains no `ollama` service.

- [ ] **Step 5: Commit**

```bash
git add infra compose.production.yml scripts
git commit -m "ops: containerize worker and scheduler"
```

### Task 8: Add full MVP acceptance E2E suite

**Files:**
- Create: `apps/web/e2e/mvp.spec.ts`
- Create: `apps/worker/tests/test_ai_contract_live_optional.py`

- [ ] **Step 1: Seed deterministic local fixtures**

Seed two users to test isolation, a digital PDF and DOCX, fake/disconnected source fixtures for CI, and deterministic fake AI adapter responses. Live provider tests remain opt-in via environment flags and never gate ordinary CI.

- [ ] **Step 2: Cover the 18 design acceptance criteria**

Playwright/worker integration must verify: email login, Google callback path at contract level, PDF/DOCX upload, schema-valid editable profile, Indonesia/Global preference, manual search, partial source success, normalization/dedup, cached requirements, hybrid match result, bucket grouping, match detail fields, original URL, Save/Applied/Ignore, XLSX/PDF request, daily scheduler, provider fallback, and cross-user data denial.

- [ ] **Step 3: Run full verification**

```bash
supabase db reset
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
pnpm --dir apps/web exec playwright test
cd apps/worker && uv run ruff check . && uv run mypy jobmatch_worker && uv run pytest -q
docker compose -f compose.production.yml config
```
Expected: all commands exit 0 with zero failing tests.

- [ ] **Step 4: Commit**

```bash
git add apps/web/e2e apps/worker/tests
git commit -m "test: verify end-to-end MVP acceptance criteria"
```

## Plan 6 acceptance checkpoint

The product can recover from worker/source/provider failures without duplicating work; daily runs are idempotent; costly endpoints are quota-limited; dead jobs are marked without destroying history; users can delete original CVs/account data; logs exclude raw CV content; Docker Compose validates for one-VPS deployment; the end-to-end suite covers all approved MVP acceptance criteria.
