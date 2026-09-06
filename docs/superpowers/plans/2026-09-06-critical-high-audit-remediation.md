# Critical and High Audit Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all ten critical and high findings in the 2026-09-06 audit, one independently tested and committed defect at a time.

**Architecture:** Preserve the approved Next.js, Supabase/PostgreSQL, and Python worker boundaries. Security and multi-write consistency move into append-only database migrations or compensating cleanup, while worker defects are locked down at their real queue/run seams and web contracts are validated end to end from request shape to queued payload.

**Tech Stack:** Next.js 16 App Router, TypeScript, Vitest, Supabase/PostgreSQL/pgtap, Python 3.12, asyncio, psycopg, Pydantic, pytest, Ruff, and mypy.

---

## File map

- `apps/worker/jobmatch_worker/scheduler.py` and `apps/worker/tests/test_scheduler.py`: PostgreSQL scheduler return contract.
- `supabase/migrations/202609060001_secure_api_usage.sql` and `supabase/tests/hardening.sql`: authenticated quota ownership.
- `apps/web/app/api/cvs/route.ts`, `apps/web/app/api/account/delete/route.ts`, `apps/web/tests/cv-upload.test.ts`, and `apps/web/tests/account-delete.test.ts`: storage compensation and safe account deletion.
- `supabase/migrations/202609060002_original_cv_retention.sql`, `apps/web/app/api/cvs/route.ts`, `apps/web/components/cv-delete-button.tsx`, `apps/web/app/cvs/page.tsx`, and `apps/web/tests/account-delete.test.ts`: original-only versus full CV deletion.
- `apps/web/app/(auth)/actions.ts` and `apps/web/tests/signup-actions.test.ts`: authenticated post-signup routing.
- `supabase/migrations/202609060003_save_candidate_profile.sql`, `supabase/tests/profiles_ai.sql`, `apps/web/lib/profile/save-profile.ts`, `apps/web/app/api/profile/route.ts`, and `apps/web/tests/profile-schema.test.ts`: atomic profile confirmation and activation.
- `apps/worker/jobmatch_worker/handlers/discovery.py` and `apps/worker/tests/test_discovery_handler.py`: result completeness, hybrid source wiring, and provenance.
- `apps/web/app/api/exports/route.ts`, `apps/web/app/exports/page.tsx`, `apps/web/components/export-request-form.tsx`, `apps/web/messages/en.json`, `apps/web/messages/id.json`, `apps/web/tests/export-request.test.ts`, `apps/web/tests/export-request-form.test.tsx`, `apps/worker/jobmatch_worker/exports/models.py`, and `apps/worker/tests/test_export_service.py`: compatible export request flow.
- `apps/worker/jobmatch_worker/handlers/matching.py` and `apps/worker/tests/test_matching_handler.py`: terminal failure accounting.

### Task 1: Repair the scheduler return contract

**Files:**
- Modify: `apps/worker/tests/test_scheduler.py`
- Modify: `apps/worker/jobmatch_worker/scheduler.py`

- [ ] **Step 1: Make the fake reproduce PostgreSQL's actual return shape**

Change `FakeConnection.execute()` so its run insert result is derived from the SQL `RETURNING` list instead of inventing identifiers. Add this assertion:

```python
async def test_run_insert_returns_every_field_used_by_queue_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection(profiles=[profile("u-1", "p-1", "c-1")])
    await schedule_daily_runs(
        conn,
        make_settings(monkeypatch),
        now_utc=datetime(2026, 8, 17, 0, 0, tzinfo=UTC),
    )

    assert conn.enqueued == [
        (
            "discover_jobs",
            "discover_jobs:run-1",
            {
                "search_run_id": "run-1",
                "search_profile_id": "p-1",
                "candidate_profile_id": "c-1",
                "user_id": "u-1",
            },
        )
    ]
```

- [ ] **Step 2: Verify the regression is red**

Run: `cd apps/worker && /tmp/workersai-tools/uv run pytest tests/test_scheduler.py::test_run_insert_returns_every_field_used_by_queue_payload -q`

Expected: failure with `KeyError: 'search_profile_id'` when the fake returns only fields named by the production SQL.

- [ ] **Step 3: Return the queue payload identifiers from PostgreSQL**

Change `RUN_INSERT_SQL` to:

```python
RUN_INSERT_SQL = """
insert into public.job_search_runs
  (user_id, search_profile_id, candidate_profile_id, trigger, idempotency_key)
values (%s, %s, %s, 'daily', %s)
on conflict (idempotency_key) do nothing
returning id, user_id, search_profile_id, candidate_profile_id
"""
```

- [ ] **Step 4: Verify focused and worker checks**

Run:

```bash
cd apps/worker
/tmp/workersai-tools/uv run pytest tests/test_scheduler.py -q
/tmp/workersai-tools/uv run ruff check jobmatch_worker/scheduler.py tests/test_scheduler.py
/tmp/workersai-tools/uv run mypy jobmatch_worker
```

Expected: 7 scheduler tests pass; Ruff and mypy exit 0.

- [ ] **Step 5: Commit**

```bash
git add apps/worker/jobmatch_worker/scheduler.py apps/worker/tests/test_scheduler.py
git diff --cached --check
git commit -m "fix: return scheduler queue identifiers"
```

### Task 2: Enforce quota ownership

**Files:**
- Create: `supabase/migrations/202609060001_secure_api_usage.sql`
- Modify: `supabase/tests/hardening.sql`

- [ ] **Step 1: Add same-user and cross-user pgtap cases**

Insert a second auth user, raise the plan count by two, and add:

```sql
select set_config(
  'request.jwt.claims',
  '{"sub":"00000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);
set local role authenticated;
select is(
  public.increment_api_usage(
    '00000000-0000-0000-0000-000000000001'::uuid,
    'manual_search'
  ),
  1,
  'authenticated user can increment their own quota'
);
select throws_ok(
  $$select public.increment_api_usage(
      '00000000-0000-0000-0000-000000000002'::uuid,
      'manual_search'
    )$$,
  '42501',
  'quota_user_mismatch',
  'authenticated user cannot increment another user quota'
);
```

- [ ] **Step 2: Verify the security regression is red**

Run: `supabase db test supabase/tests/hardening.sql`

Expected: the cross-user `throws_ok` assertion fails because the current function increments user 2.

- [ ] **Step 3: Add an append-only secure replacement**

Create the migration with:

```sql
create or replace function public.increment_api_usage(
  p_user_id uuid,
  p_action text
) returns integer
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_role text := coalesce(auth.role(), '');
  v_window timestamptz := date_trunc('day', now());
  v_count integer;
begin
  if v_role <> 'service_role' and (v_uid is null or v_uid <> p_user_id) then
    raise exception 'quota_user_mismatch' using errcode = '42501';
  end if;

  insert into public.api_usage_windows (user_id, action, window_start, count)
  values (p_user_id, p_action, v_window, 1)
  on conflict (user_id, action, window_start)
  do update set count = api_usage_windows.count + 1
  returning count into v_count;
  return v_count;
end;
$$;

revoke all on function public.increment_api_usage(uuid, text)
  from public, anon;
grant execute on function public.increment_api_usage(uuid, text)
  to authenticated, service_role;
```

- [ ] **Step 4: Verify SQL and web rate-limit callers**

Run:

```bash
supabase db reset
supabase db test supabase/tests/hardening.sql
corepack pnpm --dir apps/web test -- tests/rate-limit.test.ts
```

Expected: pgtap finishes with zero failures and the web rate-limit tests pass. If the Supabase runtime is unavailable, record that boundary and do not call the SQL behavior verified.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/202609060001_secure_api_usage.sql supabase/tests/hardening.sql
git diff --cached --check
git commit -m "fix: enforce quota ownership"
```

### Task 3: Compensate failed CV uploads and fail closed on account enumeration

**Files:**
- Create: `apps/web/tests/cv-upload.test.ts`
- Modify: `apps/web/tests/account-delete.test.ts`
- Modify: `apps/web/app/api/cvs/route.ts`
- Modify: `apps/web/app/api/account/delete/route.ts`

- [ ] **Step 1: Write storage-safety regressions**

Use mocked Supabase chains to add these behaviors:

```typescript
it.each(["path update", "queue insert"])(
  "removes the uploaded object when %s fails",
  async (failurePoint) => {
    const { response, remove, deleteCvRow } = await postCvWithFailure(failurePoint);
    expect(response.status).toBe(500);
    expect(remove).toHaveBeenCalledWith([CV_PATH]);
    expect(deleteCvRow).toHaveBeenCalled();
  },
);

it("does not delete the auth user when CV path enumeration fails", async () => {
  const { response, deleteUser } = await deleteAccountWithQueryError("cvs");
  expect(response.status).toBe(500);
  expect((await response.json()).error).toBe("storage_enumeration_failed");
  expect(deleteUser).not.toHaveBeenCalled();
});

it("does not delete the auth user when export path enumeration fails", async () => {
  const { response, deleteUser } = await deleteAccountWithQueryError("exports");
  expect(response.status).toBe(500);
  expect(deleteUser).not.toHaveBeenCalled();
});
```

The helpers must return only mock handles and fixed synthetic UUID paths; they must not log request files or paths.

- [ ] **Step 2: Verify both regressions are red**

Run: `corepack pnpm --dir apps/web test -- tests/cv-upload.test.ts tests/account-delete.test.ts`

Expected: uploaded-object removal is missing after finalization/queue failures, and enumeration errors are treated as empty lists.

- [ ] **Step 3: Add exact-object compensation**

In the CV route, add and use:

```typescript
async function cleanupFailedCv(
  client: ReturnType<typeof createServiceClient>,
  cvId: string,
  userId: string,
  storagePath: string,
): Promise<void> {
  await client.storage.from("cvs").remove([storagePath]);
  await client.rpc("delete_cv", { p_cv_id: cvId, p_user_id: userId });
}
```

Create the service client immediately after the upload succeeds. Call `cleanupFailedCv` on both `pathError` and `queueError`, preserving the original sanitized response code. Keep the existing pre-upload row deletion for upload failures.

In account deletion, destructure both results and stop before storage/auth deletion:

```typescript
const { data: cvs, error: cvListError } = await supabase.from("cvs")
  .select("storage_path").eq("user_id", user.id).not("storage_path", "is", null);
const { data: exports, error: exportListError } = await supabase.from("exports")
  .select("storage_path").eq("user_id", user.id).not("storage_path", "is", null);
if (cvListError || exportListError) {
  return NextResponse.json({ error: "storage_enumeration_failed" }, { status: 500 });
}
```

- [ ] **Step 4: Verify the affected web boundary**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/cv-upload.test.ts tests/account-delete.test.ts
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web typecheck
```

Expected: focused tests, ESLint, and TypeScript all pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/api/cvs/route.ts apps/web/app/api/account/delete/route.ts apps/web/tests/cv-upload.test.ts apps/web/tests/account-delete.test.ts
git diff --cached --check
git commit -m "fix: clean up failed CV storage writes"
```

### Task 4: Restore original-file retention behavior

**Files:**
- Create: `supabase/migrations/202609060002_original_cv_retention.sql`
- Modify: `supabase/tests/core_cv.sql`
- Modify: `apps/web/app/api/cvs/route.ts`
- Modify: `apps/web/components/cv-delete-button.tsx`
- Modify: `apps/web/app/cvs/page.tsx`
- Modify: `apps/web/tests/account-delete.test.ts`

- [ ] **Step 1: Write original-only deletion regressions**

Add a route test using `?cv_id=${CV_ID}&mode=original`:

```typescript
it("deletes only the original object and preserves the CV profile", async () => {
  const response = await deleteCv(makeRequest(CV_ID, "original"));
  expect(response.status).toBe(200);
  expect(serviceClient.rpc).toHaveBeenCalledWith("delete_original_cv", {
    p_cv_id: CV_ID,
    p_user_id: USER_ID,
  });
  expect(serviceClient.rpc).not.toHaveBeenCalledWith("delete_cv", expect.anything());
});
```

Add pgtap fixtures for a CV plus candidate profile, call `delete_original_cv`, then assert the CV and profile still exist, `storage_path is null`, and `retain_original is false`.

- [ ] **Step 2: Verify the regressions are red**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/account-delete.test.ts
supabase db test supabase/tests/core_cv.sql
```

Expected: the route calls full deletion and the SQL function is absent.

- [ ] **Step 3: Add the original-only database operation and route mode**

Create:

```sql
create or replace function public.delete_original_cv(p_cv_id uuid, p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if auth.role() <> 'service_role' then
    raise exception 'service_role_required' using errcode = '42501';
  end if;
  update public.cvs
     set storage_path = null, retain_original = false
   where id = p_cv_id and user_id = p_user_id;
end;
$$;
revoke all on function public.delete_original_cv(uuid, uuid) from public, anon, authenticated;
grant execute on function public.delete_original_cv(uuid, uuid) to service_role;
```

The route validates `mode` as `original | full`, removes the private object first, calls `delete_original_cv` for `original`, and retains `delete_cv` for explicit full deletion. Select `storage_path` on the CV page and render separate original-file and full-CV buttons; the original button is absent when `storage_path` is null.

- [ ] **Step 4: Verify DB, route, and UI**

Run:

```bash
supabase db reset
supabase db test supabase/tests/core_cv.sql
corepack pnpm --dir apps/web test -- tests/account-delete.test.ts
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web typecheck
```

Expected: original-only deletion preserves profile fixtures; web checks pass.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/202609060002_original_cv_retention.sql supabase/tests/core_cv.sql apps/web/app/api/cvs/route.ts apps/web/components/cv-delete-button.tsx apps/web/app/cvs/page.tsx apps/web/tests/account-delete.test.ts
git diff --cached --check
git commit -m "fix: preserve profiles when deleting original CVs"
```

### Task 5: Keep successful signups authenticated

**Files:**
- Create: `apps/web/tests/signup-actions.test.ts`
- Modify: `apps/web/app/(auth)/actions.ts`

- [x] **Step 1: Add redirect-contract tests**

Mock `createClient` and `redirect`; because Next.js redirects throw, assert the destination:

```typescript
it("redirects a signup with a session to the dashboard without signing out", async () => {
  signUpWithPassword.mockResolvedValue({
    data: { user: { id: USER_ID }, session: { access_token: "test" } },
    error: null,
  });
  await expect(signUp(validFormData())).rejects.toThrow("NEXT_REDIRECT:/dashboard");
  expect(signOut).not.toHaveBeenCalled();
});

it("sends a sessionless signup to login", async () => {
  signUpWithPassword.mockResolvedValue({ data: { user: { id: USER_ID }, session: null }, error: null });
  await expect(signUp(validFormData())).rejects.toThrow("NEXT_REDIRECT:/login?registered=1");
});
```

- [x] **Step 2: Verify the authenticated case is red**

Run: `corepack pnpm --dir apps/web test -- tests/signup-actions.test.ts`

Expected: dashboard assertion fails and `signOut` is called.

- [x] **Step 3: Branch on the Supabase session**

Read the Next 16 redirect guide at `apps/web/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/redirect.md`, then change the action to:

```typescript
const { data, error } = await supabase.auth.signUp({ email, password });
if (error?.code === "user_already_exists") redirect("/register?error=email_taken");
if (error) redirect("/register?error=signup_failed");
if (data.session) redirect("/dashboard");
redirect("/login?registered=1");
```

- [x] **Step 4: Verify auth and runtime checks**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/signup-actions.test.ts tests/auth.test.ts
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web typecheck
```

Expected: all focused tests and checks pass.

- [x] **Step 5: Commit**

```bash
git add 'apps/web/app/(auth)/actions.ts' apps/web/tests/signup-actions.test.ts
git diff --cached --check
git commit -m "fix: keep new users signed in"
```

### Task 6: Save confirmed profiles and activation atomically

**Files:**
- Create: `supabase/migrations/202609060003_save_candidate_profile.sql`
- Modify: `supabase/tests/profiles_ai.sql`
- Modify: `apps/web/lib/profile/save-profile.ts`
- Modify: `apps/web/app/api/profile/route.ts`
- Modify: `apps/web/tests/profile-schema.test.ts`

- [x] **Step 1: Write transaction and repository regressions**

Add pgtap coverage that saves a new confirmed version and activates its CV, then force an activation failure and assert neither a new profile version nor active-CV state changed. Replace the multi-method fake expectation with one RPC expectation:

```typescript
it("saves and activates through one database operation", async () => {
  const rpc = vi.fn().mockResolvedValue({ data: 3, error: null });
  const result = await saveCandidateProfile({ rpc } as never, {
    userId: "u1",
    cvId: "cv-1",
    profile: baseProfile(),
  });
  expect(result).toEqual({ ok: true, version: 3 });
  expect(rpc).toHaveBeenCalledTimes(1);
  expect(rpc).toHaveBeenCalledWith("save_candidate_profile", {
    p_cv_id: "cv-1",
    p_profile: baseProfile(),
  });
});
```

- [x] **Step 2: Verify the single-operation contract is red**

Run: `corepack pnpm --dir apps/web test -- tests/profile-schema.test.ts`

Expected: current repository performs separate insert, clear, and activate calls.

- [x] **Step 3: Add the authenticated transaction function**

Implement `save_candidate_profile(p_cv_id uuid, p_profile jsonb) returns integer` in the migration. It must:

```sql
v_user_id := auth.uid();
if v_user_id is null then
  raise exception 'unauthorized' using errcode = '42501';
end if;
perform 1 from public.cvs where id = p_cv_id and user_id = v_user_id for update;
if not found then
  raise exception 'cv_not_found' using errcode = 'P0001';
end if;
select coalesce(max(version), 0) + 1 into v_version
from public.candidate_profiles where cv_id = p_cv_id;
insert into public.candidate_profiles(user_id, cv_id, version, profile, confirmed_at)
values (v_user_id, p_cv_id, v_version, p_profile, now());
update public.cvs set is_active = false where user_id = v_user_id and id <> p_cv_id and is_active;
update public.cvs set is_active = true where id = p_cv_id and user_id = v_user_id;
update public.search_profiles set candidate_profile_id = (
  select id from public.candidate_profiles where cv_id = p_cv_id and version = v_version
) where user_id = v_user_id and is_current;
return v_version;
```

Revoke public/anon execution and grant authenticated execution. Replace `ProfileRepo` with a single `rpc` dependency and map PostgreSQL errors to the existing safe HTTP statuses.

- [x] **Step 4: Verify atomicity and web contracts**

Run:

```bash
supabase db reset
supabase db test supabase/tests/profiles_ai.sql
corepack pnpm --dir apps/web test -- tests/profile-schema.test.ts
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web typecheck
```

Expected: rollback and success pgtap assertions pass; web tests and checks pass.

- [x] **Step 5: Commit**

```bash
git add supabase/migrations/202609060003_save_candidate_profile.sql supabase/tests/profiles_ai.sql apps/web/lib/profile/save-profile.ts apps/web/app/api/profile/route.ts apps/web/tests/profile-schema.test.ts
git diff --cached --check
git commit -m "fix: save profiles and active CV atomically"
```

### Task 7: Remove the two-job discovery truncation

**Files:**
- Modify: `apps/worker/tests/test_discovery_handler.py`
- Modify: `apps/worker/jobmatch_worker/handlers/discovery.py`

- [x] **Step 1: Change the acceptance-shaped assertion to four distinct jobs**

In `test_discovery_run_keeps_successful_sources_when_one_fails`, assert:

```python
assert final_update[1:5] == (5, 4, 1, 1)
assert len(job_inserts) == 4
assert len(provenance) == 5
```

Keep five unique-normalized inputs with one duplicate URL and one failed source so the counts mean discovered, normalized, duplicate, failed.

- [x] **Step 2: Verify the regression is red**

Run: `cd apps/worker && /tmp/workersai-tools/uv run pytest tests/test_discovery_handler.py::test_discovery_run_keeps_successful_sources_when_one_fails -q`

Expected: only two jobs are inserted and extra distinct jobs are counted as duplicates.

- [x] **Step 3: Remove output truncation**

Delete `_MAX_JOBS_PER_RUN` and this block only:

```python
if len(kept) > _MAX_JOBS_PER_RUN:
    duplicate_count += len(kept) - _MAX_JOBS_PER_RUN
    kept = kept[:_MAX_JOBS_PER_RUN]
```

Keep `_MAX_SOURCE_RESULTS` and `_MAX_CAREER_CANDIDATES` unchanged.

- [x] **Step 4: Verify discovery checks**

Run:

```bash
cd apps/worker
/tmp/workersai-tools/uv run pytest tests/test_discovery_handler.py -q
/tmp/workersai-tools/uv run ruff check jobmatch_worker/handlers/discovery.py tests/test_discovery_handler.py
/tmp/workersai-tools/uv run mypy jobmatch_worker
```

Expected: discovery tests, Ruff, and mypy pass.

- [x] **Step 5: Commit**

```bash
git add apps/worker/jobmatch_worker/handlers/discovery.py apps/worker/tests/test_discovery_handler.py
git diff --cached --check
git commit -m "fix: retain all distinct discovery results"
```

### Task 8: Wire hybrid sources and preserve duplicate provenance

**Files:**
- Modify: `apps/worker/tests/test_discovery_handler.py`
- Modify: `apps/worker/jobmatch_worker/handlers/discovery.py`

- [x] **Step 1: Write source-builder and provenance regressions**

Change the source-builder expectation and add provenance assertions:

```python
assert set(sources) == {"tavily", "greenhouse", "lever"}
assert sources["greenhouse"].source_key == "greenhouse"
assert sources["lever"].source_key == "lever"

source_keys = [params[3] for params in provenance]
assert source_keys.count("greenhouse") == 3
assert source_keys.count("tavily") == 2
assert {params[0] for params in provenance if params[3] in {"greenhouse", "tavily"}}
```

The duplicate fixture must include the same canonical job once from Greenhouse and once from Tavily, plus other distinct jobs. Assert both source keys map to the same persisted `job_id`.

- [x] **Step 2: Verify both regressions are red**

Run:

```bash
cd apps/worker
/tmp/workersai-tools/uv run pytest tests/test_discovery_handler.py::test_build_sources_uses_tavily_for_web_search tests/test_discovery_handler.py::test_discovery_run_keeps_successful_sources_when_one_fails -q
```

Expected: production builder exposes only Tavily and duplicate provenance is absent.

- [x] **Step 3: Construct all connectors and pass all normalized jobs**

Import the ATS connectors and implement:

```python
def _build_sources(settings: Settings) -> dict[str, SourceConnector]:
    return {
        "tavily": TavilyConnector(api_key=settings.tavily_api_key),
        "greenhouse": GreenhouseConnector(
            board_token=settings.greenhouse_board_token
        ),
        "lever": LeverConnector(site_name=settings.lever_site_name),
    }
```

Change the provenance call to:

```python
await _persist_provenance(
    conn,
    run_id=run_id,
    all_jobs=normalized,
    kept_jobs=kept,
    job_ids=upsert_result.job_ids,
)
```

Do not catch configuration failures in `_build_sources`; each connector reports `SourceConfigError` inside `_run_source`, preserving source isolation and final `PARTIAL` accounting.

- [x] **Step 4: Verify the complete discovery subsystem**

Run:

```bash
cd apps/worker
/tmp/workersai-tools/uv run pytest tests/test_discovery_handler.py tests/test_job_connectors.py tests/test_job_dedupe.py -q
/tmp/workersai-tools/uv run ruff check jobmatch_worker tests/test_discovery_handler.py
/tmp/workersai-tools/uv run mypy jobmatch_worker
```

Expected: all selected tests and static checks pass.

- [x] **Step 5: Commit**

```bash
git add apps/worker/jobmatch_worker/handlers/discovery.py apps/worker/tests/test_discovery_handler.py
git diff --cached --check
git commit -m "fix: enable hybrid discovery provenance"
```

### Task 9: Align export filters and add request controls

**Files:**
- Modify: `apps/web/app/api/exports/route.ts`
- Create: `apps/web/components/export-request-form.tsx`
- Modify: `apps/web/app/exports/page.tsx`
- Modify: `apps/web/messages/en.json`
- Modify: `apps/web/messages/id.json`
- Modify: `apps/web/tests/export-request.test.ts`
- Create: `apps/web/tests/export-request-form.test.tsx`
- Modify: `apps/worker/tests/test_export_service.py`

- [ ] **Step 1: Write cross-runtime contract and UI tests**

In the route test, submit and assert persistence of:

```typescript
filters: {
  region: ["indonesia"],
  work_mode: ["remote"],
  min_score: 80,
  status: ["saved"],
}
```

Assert `exportsInsert` receives this exact `filter_json`. In Python add:

```python
def test_web_shaped_export_filters_validate() -> None:
    filters = ExportFilters.model_validate({
        "region": ["indonesia"],
        "work_mode": ["remote"],
        "min_score": 80,
        "status": ["saved"],
    })
    assert filters.region == ["indonesia"]
```

Render `ExportRequestForm` with a run id, click Excel and PDF actions, assert `POST /api/exports` receives the chosen format, and assert pending/error/success text is accessible.

- [ ] **Step 2: Verify the scalar/list and missing-control failures**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/export-request.test.ts tests/export-request-form.test.tsx
cd apps/worker && /tmp/workersai-tools/uv run pytest tests/test_export_service.py::test_web_shaped_export_filters_validate -q
```

Expected: the web schema rejects region arrays and the form module is absent; the worker contract test passes and defines the target shape.

- [ ] **Step 3: Implement the shared request shape and form**

Change web `region` validation to:

```typescript
region: z.array(z.enum(["indonesia", "global"])).max(2).optional(),
```

Implement `ExportRequestForm` as a client component with `runId`, optional current filters, two format buttons, disabled pending state, a sanitized error message, and `router.refresh()` after HTTP 202. The request body is:

```typescript
{
  searchRunId: runId,
  format,
  scope: filters ? "current_filters" : "all",
  filters: filters ?? undefined,
}
```

Read `apps/web/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md` before implementing the boundary. On the server page, query the newest owned search run id and render the form above the list. Add identical key sets to both locale files: `createXlsx`, `createPdf`, `creating`, `requestAccepted`, and `requestFailed`.

- [ ] **Step 4: Verify export behavior and Next build**

Run:

```bash
corepack pnpm --dir apps/web test -- tests/export-request.test.ts tests/export-request-form.test.tsx
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web build
cd apps/worker
/tmp/workersai-tools/uv run pytest tests/test_export_service.py tests/test_excel_export.py tests/test_pdf_export.py -q
/tmp/workersai-tools/uv run ruff check jobmatch_worker/exports tests/test_export_service.py
/tmp/workersai-tools/uv run mypy jobmatch_worker
```

Expected: web tests/lint/typecheck/build and worker export tests/static checks pass.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/api/exports/route.ts apps/web/components/export-request-form.tsx apps/web/app/exports/page.tsx apps/web/messages/en.json apps/web/messages/id.json apps/web/tests/export-request.test.ts apps/web/tests/export-request-form.test.tsx apps/worker/tests/test_export_service.py
git diff --cached --check
git commit -m "fix: align export filters and request controls"
```

### Task 10: Finalize matching runs after provider unavailability

**Files:**
- Modify: `apps/worker/tests/test_matching_handler.py`
- Modify: `apps/worker/jobmatch_worker/handlers/matching.py`

- [ ] **Step 1: Write no-provider terminal-accounting tests**

Add one test for requirement extraction and one for direct matching:

```python
@pytest.mark.asyncio
async def test_match_job_without_provider_completes_run_accounting() -> None:
    connection = _Connection(
        run_row={"user_id": "user-1", "candidate_profile_id": "prof-1", "locations": []},
        profile_row={"profile": PROFILE_JSON},
        job_row={"description": "Python required"},
        pending=0,
        failed=1,
    )
    await handle_match_job(
        connection,
        {"id": "item-no-provider", "payload": {"search_run_id": "run-9", "job_id": "job-9"}},
        _settings(),
    )
    assert any(
        params[0] in {"partial", "failed"} and params[2] == "run-9"
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    )
```

For requirement extraction, configure `_RUNS_FOR_JOB_SQL` to return the affected run and assert it receives a terminal run update after the work item fails.

- [ ] **Step 2: Verify both paths are red**

Run: `cd apps/worker && /tmp/workersai-tools/uv run pytest tests/test_matching_handler.py -k 'without_provider' -q`

Expected: the item is failed but no run completion update is executed.

- [ ] **Step 3: Call completion accounting before each no-provider return**

Use the same helpers already used by other terminal errors:

```python
if not providers:
    await fail_item(conn, item_id, "no AI providers configured")
    await _complete_runs_for_job_if_terminal(conn, str(job_id))
    return
```

and:

```python
if not providers:
    await fail_item(conn, item_id, "no AI providers configured")
    await _complete_run_if_terminal(conn, str(run_id), current_item_id=item_id)
    return
```

If the run has no successful matches, update `_complete_run_if_terminal` to select the successful match count and choose `failed` for zero successes plus failures, `partial` for successes plus failures, and `completed` for no failures.

- [ ] **Step 4: Verify matching and worker checks**

Run:

```bash
cd apps/worker
/tmp/workersai-tools/uv run pytest tests/test_matching_handler.py tests/test_matching_service.py tests/test_golden_matching.py -q
/tmp/workersai-tools/uv run ruff check jobmatch_worker/handlers/matching.py tests/test_matching_handler.py
/tmp/workersai-tools/uv run mypy jobmatch_worker
```

Expected: all matching tests and static checks pass.

- [ ] **Step 5: Commit**

```bash
git add apps/worker/jobmatch_worker/handlers/matching.py apps/worker/tests/test_matching_handler.py
git diff --cached --check
git commit -m "fix: finalize runs after provider failure"
```

### Task 11: Run the full verification matrix

**Files:**
- Verify only; modify documentation only if a command or environment boundary must be recorded.

- [ ] **Step 1: Run all available web gates**

```bash
corepack pnpm --dir apps/web test
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web build
```

Expected: 0 failed tests and every command exits 0.

- [ ] **Step 2: Run all worker gates**

```bash
cd apps/worker
/tmp/workersai-tools/uv run pytest
/tmp/workersai-tools/uv run ruff check .
/tmp/workersai-tools/uv run mypy jobmatch_worker
```

Expected: 0 failed tests; only the three explicitly gated live-provider tests may skip; Ruff and mypy exit 0.

- [ ] **Step 3: Run database, Compose, and E2E gates when available**

```bash
supabase db reset
supabase db test
docker compose -f compose.production.yml config
corepack pnpm --dir apps/web exec playwright test
```

Expected: migrations apply, pgtap has 0 failures, Compose exits 0 without an Ollama service, and authenticated E2E passes. Report missing executables, unavailable daemons, or absent seeded services as unverified boundaries.

- [ ] **Step 4: Check secrets, whitespace, and requirement coverage**

```bash
git diff --check origin/main...HEAD
git grep -nEI '(SUPABASE_SERVICE_ROLE_KEY|OLLAMA_API_KEY|OPENROUTER_API_KEY|NVIDIA_API_KEY)=[^$<{[:space:]]+' -- ':!*.example' ':!docs/**'
git log --oneline origin/main..HEAD
```

Expected: whitespace check is clean, secret scan prints no tracked credentials, and history contains the design plus ten ordered fix commits.

- [ ] **Step 5: Record final status**

Re-read `docs/superpowers/specs/2026-09-06-critical-high-audit-remediation-design.md` and this plan. Check off only requirements supported by fresh command output. Report any unavailable integration boundary separately from code/test failures.
