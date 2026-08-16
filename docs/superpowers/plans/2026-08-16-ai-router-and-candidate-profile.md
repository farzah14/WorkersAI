# AI Router and Candidate Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert extracted CV text into an editable, schema-valid candidate profile while automatically falling back across NVIDIA NIM, OpenRouter, and Ollama Cloud.

**Architecture:** The Python worker owns a provider-neutral `AiProvider` contract. All providers receive the same prompt/schema and return Pydantic-validated structured output; a router applies timeout, retry, circuit-breaker, and fallback rules and records sanitized operational metadata.

**Tech Stack:** Python 3.12, Pydantic, HTTPX, PostgreSQL, NVIDIA NIM/OpenAI-compatible API, OpenRouter, Ollama Cloud HTTP API, pytest, Next.js/Supabase for profile review UI.

---

## File structure locked by this plan

```text
apps/worker/jobmatch_worker/
├── ai/{base,router,nvidia,openrouter,ollama}.py
├── ai/circuit_breaker.py
├── profiles/{models,prompt,extract}.py
└── handlers/profile.py
apps/web/
├── app/onboarding/profile/page.tsx
├── app/api/profile/route.ts
└── lib/profile/schema.ts
supabase/migrations/202608160002_profiles_ai.sql
```

### Task 1: Add candidate-profile and AI audit schema

**Files:**
- Create: `supabase/migrations/202608160002_profiles_ai.sql`
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
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/profiles_ai.sql
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

### Task 3: Implement NVIDIA, OpenRouter, and Ollama adapters

Before Step 1 run:
```bash
cd apps/worker && uv add --dev pytest-httpx
```

**Files:**
- Create: `apps/worker/jobmatch_worker/ai/nvidia.py`
- Create: `apps/worker/jobmatch_worker/ai/openrouter.py`
- Create: `apps/worker/jobmatch_worker/ai/ollama.py`
- Test: `apps/worker/tests/test_ai_adapters.py`

- [ ] **Step 1: Write failing mocked HTTP contract tests**

Each adapter test must assert the configured model, non-streaming behavior, provider-specific authorization, and returned `AiResult.data`. NVIDIA/OpenRouter tests assert their supported structured-output request fields. Ollama Cloud tests assert Bearer authentication, the cloud base URL, JSON-only prompting, JSON parsing, and application-side schema validation rather than assuming native JSON-schema enforcement.

Example:
```python
@pytest.mark.asyncio
async def test_openrouter_uses_json_schema(httpx_mock):
    httpx_mock.add_response(json={"choices":[{"message":{"content":"{\\"ok\\":true}"}}]})
    provider = OpenRouterProvider(api_key="x", model="free-model", client=httpx.AsyncClient())
    result = await provider.generate_structured(system="s", user="u", schema={"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]})
    assert result.data == {"ok": True}
```
Expected first run: FAIL.

- [ ] **Step 2: Implement OpenRouter adapter**

Send `POST https://openrouter.ai/api/v1/chat/completions` with `response_format.type='json_schema'`, strict schema, `stream=false`, timeout from settings, and parse `choices[0].message.content` as JSON. Treat HTTP 408/429/5xx as retryable; 400/401/403 as permanent configuration/input errors.

- [ ] **Step 3: Implement NVIDIA NIM adapter**

Use the configured OpenAI-compatible NIM base URL. Send the schema using NIM structured-generation fields supported by the selected endpoint/model; keep this translation inside `nvidia.py` so callers remain provider-neutral. Validate the response with the same Pydantic schema after JSON parsing.

- [ ] **Step 4: Implement Ollama Cloud adapter**

Update `.env.example` and worker settings with server-only `OLLAMA_API_KEY`, `OLLAMA_BASE_URL=https://ollama.com/api`, and required `OLLAMA_MODEL`. Do not provide a hardcoded model default. When `ollama` is present in `AI_PROVIDER_ORDER`, startup validation must require both the API key and model identifier.

Implement the cloud request without a local daemon dependency:
```python
schema_text = json.dumps(schema, separators=(",", ":"))
payload = {
    "model": self.model,
    "stream": False,
    "options": {"temperature": 0},
    "messages": [
        {
            "role": "system",
            "content": f"{system}\nReturn JSON only. It must satisfy this JSON Schema: {schema_text}",
        },
        {"role": "user", "content": user},
    ],
}
response = await self.client.post(
    f"{self.base_url.rstrip('/')}/chat",
    headers={"Authorization": f"Bearer {self.api_key}"},
    json=payload,
    timeout=self.timeout,
)
response.raise_for_status()
body = response.json()
data = json.loads(body["message"]["content"])
```

Validate `data` against the caller-supplied Pydantic/JSON schema in the common adapter path. Invalid JSON or schema-invalid output is a retryable structured-output failure according to the bounded router policy. Never call `localhost:11434`, pull a model, or start an Ollama container.

- [ ] **Step 5: Run adapter tests and commit**

```bash
cd apps/worker && uv run pytest tests/test_ai_adapters.py -q
git add apps/worker && git commit -m "feat: add three ai provider adapters"
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
    nvidia = FakeProvider("nvidia", retryable=True)
    openrouter = FakeProvider("openrouter", data={"ok": True})
    ollama = FakeProvider("ollama", data={"ok": True})
    result = await AiRouter([nvidia, openrouter, ollama]).generate_structured(system="s", user="u", schema=SCHEMA)
    assert result.provider == "openrouter"

@pytest.mark.asyncio
async def test_router_does_not_fallback_on_invalid_business_input():
    nvidia = FakeProvider("nvidia", permanent=True)
    with pytest.raises(PermanentAiError):
        await AiRouter([nvidia]).generate_structured(system="s", user="u", schema=SCHEMA)
```
Expected: FAIL.

- [ ] **Step 2: Implement circuit state**

Use states `closed`, `open`, `half_open`. Open after 3 consecutive retryable provider failures for 60 seconds; allow one half-open probe; close on success. Keep state in-process for MVP and expose it via metrics later in Plan 6.

- [ ] **Step 3: Implement router rules**

Default order comes from env `AI_PROVIDER_ORDER=nvidia,ollama,openrouter`. Each provider receives one immediate call plus at most one retry with jitter for transport/429/5xx errors. Schema validation failure is retryable once on the same provider, then falls back. Invalid CV/input validation errors never enter the router.

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
