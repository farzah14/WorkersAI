# AI Router and Candidate Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert extracted CV text into an editable, schema-valid candidate profile through the configured 9Router gateway with bounded retry and circuit handling.

**Architecture:** The Python worker owns a provider-neutral `AiProvider` contract. All providers receive the same prompt/schema and return Pydantic-validated structured output; a router applies timeout, retry, circuit-breaker, and fallback rules and records sanitized operational metadata.

**Tech Stack:** Python 3.12, Pydantic, HTTPX, PostgreSQL, 9Router OpenAI-compatible HTTP API, pytest, Next.js/Supabase for profile review UI.

> **Current implementation amendment (2026-09-09):** The provider adapter task
> below is historical design text. The shipped implementation has one
> `NineRouterProvider` in `ai/ninerouter.py`; do not create or restore
> `nvidia.py`, `openrouter.py`, or `ollama.py`, and do not add those provider
> names to `AI_PROVIDER_ORDER`. The router's fallback boundary is the configured
> 9Router gateway and its circuit/retry policy. The current source of truth for
> deployment and provider configuration is `AGENTS.md` plus `docs/AI-PROVIDERS.md`.

---

## File structure locked by this plan

```text
apps/worker/jobmatch_worker/
├── ai/{base,router,ninerouter}.py
├── ai/circuit_breaker.py
├── profiles/{models,prompt,extract}.py
└── handlers/profile.py
apps/web/
├── app/onboarding/profile/page.tsx
├── app/api/profile/route.ts
└── lib/profile/schema.ts
supabase/migrations/202608160004_profiles_ai.sql
```

### Task 1: Add candidate-profile and AI audit schema

**Files:**
- Create: `supabase/migrations/202608160004_profiles_ai.sql`
- Test: `supabase/tests/profiles_ai.sql`

- [ ] **Step 1: Write failing table assertions**

```sql
begin;
select 1 / (case when to_regclass('public.candidate_profiles') is not null then 1 else 0 end);
select 1 / (case when to_regclass('public.ai_requests') is not null then 1 else 0 end);
rollback;
```
Expected before migration: FAIL.

- [ ] **Step 2: Implement versioned profiles and AI request metadata**

```sql
create table public.candidate_profiles (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  cv_id uuid not null references public.cvs(id) on delete cascade,
  version integer not null,
  profile jsonb not null,
  confirmed_at timestamptz,
  created_at timestamptz not null default now(),
  unique(cv_id, version)
);

create table public.ai_requests (
  id uuid primary key default gen_random_uuid(),
  operation text not null,
  provider text not null,
  model text not null,
  status text not null check (status in ('success','retryable_failure','permanent_failure','skipped_circuit_open')),
  latency_ms integer,
  fallback_from text,
  error_code text,
  created_at timestamptz not null default now()
);

alter table public.candidate_profiles enable row level security;
revoke all on public.ai_requests from anon, authenticated;
create policy candidate_profiles_owner_all on public.candidate_profiles
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
```

- [ ] **Step 3: Reset DB and verify**

Run:
```bash
supabase db reset
supabase db test supabase/tests/profiles_ai.sql
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add supabase
git commit -m "feat: add candidate profile and ai audit schema"
```

### Task 2: Define provider-neutral structured-output contracts

**Files:**
- Create: `apps/worker/jobmatch_worker/ai/base.py`
- Create: `apps/worker/jobmatch_worker/profiles/models.py`
- Test: `apps/worker/tests/test_profile_models.py`

- [ ] **Step 1: Write failing model-validation tests**

```python
import pytest
from pydantic import ValidationError
from jobmatch_worker.profiles.models import CandidateProfile

def test_candidate_profile_requires_roles_and_skills() -> None:
    profile = CandidateProfile.model_validate({
        "name": "Ada",
        "current_role": "Data Engineer",
        "seniority": "mid",
        "target_roles": ["Data Engineer"],
        "skills": ["Python", "SQL"],
        "experience_years": 4.0,
        "languages": ["English", "Indonesian"],
        "education": ["BSc Computer Science"],
    })
    assert profile.target_roles == ["Data Engineer"]

    with pytest.raises(ValidationError):
        CandidateProfile.model_validate({"name": "Ada", "target_roles": [], "skills": []})
```
Expected first run: FAIL.

- [ ] **Step 2: Implement models and provider protocol**

```python
# profiles/models.py
from typing import Literal
from pydantic import BaseModel, Field

class CandidateProfile(BaseModel):
    name: str | None = None
    current_role: str | None = None
    seniority: Literal["intern","junior","mid","senior","lead","manager","executive","unknown"] = "unknown"
    target_roles: list[str] = Field(min_length=1)
    skills: list[str] = Field(min_length=1)
    experience_years: float | None = Field(default=None, ge=0, le=80)
    languages: list[str] = []
    education: list[str] = []
```

```python
# ai/base.py
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass(frozen=True)
class AiResult:
    provider: str
    model: str
    data: dict[str, Any]
    latency_ms: int

class AiProvider(Protocol):
    name: str
    async def generate_structured(self, *, system: str, user: str, schema: dict[str, Any]) -> AiResult: ...
```

- [ ] **Step 3: Run tests**

```bash
cd apps/worker && uv run pytest tests/test_profile_models.py -q
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/worker
git commit -m "feat: define candidate profile and ai contracts"
```

### Task 3: Implement the configured 9Router adapter

**Files:**
- Existing: `apps/worker/jobmatch_worker/ai/ninerouter.py`
- Existing: `apps/worker/jobmatch_worker/ai/router.py`
- Test: `apps/worker/tests/test_ai_adapters.py`

- [ ] **Step 1: Write failing mocked HTTP contract tests**

The adapter test must assert the configured model, non-streaming behavior,
optional bearer authorization, the OpenAI-compatible endpoint, and returned
`AiResult.data`. The application must parse and validate the response rather
than trusting gateway-native schema enforcement.

Example:
```python
@pytest.mark.asyncio
async def test_ninerouter_uses_configured_model(httpx_mock):
    httpx_mock.add_response(json={"choices":[{"message":{"content":"{\\"ok\\":true}"}}]})
    provider = NineRouterProvider(api_key="x", model="configured-model", base_url="http://gateway/v1", client=httpx.AsyncClient())
    result = await provider.generate_structured(system="s", user="u", schema={"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]})
    assert result.data == {"ok": True}
```
Expected first run: FAIL.

- [ ] **Step 2: Verify the 9Router request**

Send `POST {NINEROUTER_BASE_URL}/chat/completions` with the configured model,
non-streaming JSON output, bounded timeout, and optional bearer authorization.
Parse `choices[0].message.content` as JSON and classify HTTP 408/429/5xx as
retryable; 400/401/403 as permanent configuration/input errors.

- [ ] **Step 3: Verify application-side schema validation**

Validate parsed response data against the caller-supplied schema in the common
router path. Do not add provider-specific adapters or model names.

- [ ] **Step 4: Keep the gateway cloud/local boundary explicit**

Use only the configured 9Router endpoint. Never call `localhost:11434`, pull a
model, or start an Ollama container. Validate parsed response data against the
caller-supplied Pydantic/JSON schema in the common router path.

- [ ] **Step 5: Run adapter tests and commit**

```bash
cd apps/worker && uv run pytest tests/test_ai_adapters.py -q
git add apps/worker && git commit -m "test: verify 9router adapter contract"
```
Expected: PASS.

### Task 4: Implement fallback router, retry policy, and circuit breaker

**Files:**
- Create: `apps/worker/jobmatch_worker/ai/circuit_breaker.py`
- Create: `apps/worker/jobmatch_worker/ai/router.py`
- Test: `apps/worker/tests/test_ai_router.py`

- [ ] **Step 1: Write failing fallback tests**

```python
@pytest.mark.asyncio
async def test_router_falls_back_on_retryable_failure():
    gateway = FakeProvider("9router", retryable=True)
    result = await AiRouter([gateway]).generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "9router"

@pytest.mark.asyncio
async def test_router_does_not_fallback_on_invalid_business_input():
    gateway = FakeProvider("9router", permanent=True)
    with pytest.raises(PermanentAiError):
        await AiRouter([gateway]).generate_structured(system="s", user="u", schema=SCHEMA)
```
Expected: FAIL.

- [ ] **Step 2: Implement circuit state**

Use states `closed`, `open`, `half_open`. Open after 3 consecutive retryable provider failures for 60 seconds; allow one half-open probe; close on success. Keep state in-process for MVP and expose it via metrics later in Plan 6.

- [ ] **Step 3: Implement router rules**

Default order comes from env `AI_PROVIDER_ORDER=9router`. The configured
gateway receives one immediate call plus at most one retry with jitter for
transport/429/5xx errors. Schema validation failure is retryable once on the
same gateway, then the operation fails. Invalid CV/input validation errors
never enter the router.

- [ ] **Step 4: Persist AI request metadata**

After every attempt, insert `ai_requests` with operation, provider, model, status, latency, fallback source, and sanitized error code. Do not persist prompt, CV text, or model response by default.

- [ ] **Step 5: Run tests and commit**

```bash
cd apps/worker && uv run pytest tests/test_ai_router.py -q
git add apps/worker && git commit -m "feat: add configurable ai fallback router"
```
Expected: PASS.

### Task 5: Extract candidate profile through the router

**Files:**
- Create: `apps/worker/jobmatch_worker/profiles/prompt.py`
- Create: `apps/worker/jobmatch_worker/profiles/extract.py`
- Create: `apps/worker/jobmatch_worker/handlers/profile.py`
- Test: `apps/worker/tests/test_profile_extract.py`

- [ ] **Step 1: Write failing extraction test**

```python
@pytest.mark.asyncio
async def test_profile_extraction_validates_router_output():
    router = FakeRouter({
        "name":"Ada", "current_role":"Data Engineer", "seniority":"mid",
        "target_roles":["Data Engineer"], "skills":["Python","SQL"],
        "experience_years":4, "languages":["English"], "education":["BSc"]
    })
    profile = await extract_candidate_profile("Ada has 4 years...", router)
    assert profile.seniority == "mid"
```
Expected: FAIL.

- [ ] **Step 2: Implement a data-only prompt**

System prompt rules must state: extract only facts supported by CV text; use `unknown`/null when absent; do not invent credentials; infer target roles conservatively from actual experience; output only the supplied schema.

- [ ] **Step 3: Implement work-item chaining**

When `extract_cv` completes, enqueue `extract_candidate_profile:<cv_id>:<content_hash>`. Handler calls the router, validates `CandidateProfile`, inserts version `1` (or next version if reparsed), and leaves `confirmed_at` null for user review.

- [ ] **Step 4: Run tests and commit**

```bash
cd apps/worker && uv run pytest tests/test_profile_extract.py -q
git add apps/worker && git commit -m "feat: extract schema-valid candidate profiles"
```
Expected: PASS.

### Task 6: Build profile review/edit and one-active-CV workflow

**Files:**
- Create: `apps/web/lib/profile/schema.ts`
- Create: `apps/web/app/onboarding/profile/page.tsx`
- Create: `apps/web/app/api/profile/route.ts`
- Modify: `apps/web/app/cvs/page.tsx`
- Test: `apps/web/tests/profile-schema.test.ts`

- [ ] **Step 1: Write failing client/server schema tests**

Use Zod with the same enum and required fields as Pydantic. Test that empty `target_roles`/`skills` fail and supported seniority values pass.

- [ ] **Step 2: Implement profile form**

Render editable name/current role/seniority/target roles/skills/experience/languages/education. On save, create a new `candidate_profiles.version` rather than overwriting prior versions, set `confirmed_at=now()`, and make that CV active in one transaction by first clearing existing `is_active` for the user and then setting selected CV true.

- [ ] **Step 3: Ensure active-CV uniqueness error is user-safe**

Translate PostgreSQL unique-index violations into HTTP 409 with `{"error":"active_cv_conflict"}`; retry the transaction once after re-reading the current active CV.

- [ ] **Step 4: Verify tests and commit**

```bash
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
git add apps/web && git commit -m "feat: add editable candidate profile onboarding"
```
Expected: PASS.

## Plan 2 acceptance checkpoint

Run all web/worker tests and a provider-router integration test with two fake failing providers plus one successful fake provider. Manual smoke: upload a digital CV, text extraction completes, candidate profile appears for review, user edits/accepts it, and exactly one CV is active. Confirm `ai_requests` contains provider/latency/fallback metadata but no raw CV text.
