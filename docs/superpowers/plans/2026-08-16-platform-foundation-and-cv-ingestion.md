# Platform Foundation and CV Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deployable foundation where users can authenticate, privately upload PDF/DOCX CVs, and have a durable worker extract text without OCR.

**Architecture:** Next.js 16 runs on Vercel and uses Supabase SSR auth, Postgres, and private Storage. A Python worker on the future VPS polls a PostgreSQL `work_items` queue with `FOR UPDATE SKIP LOCKED`, extracts text, and records durable status so requests are resumable and idempotent.

**Tech Stack:** Next.js 16, TypeScript, Tailwind CSS, Supabase Auth/Postgres/Storage, pnpm, Vitest, Playwright, Python 3.12, uv, psycopg, PyMuPDF, python-docx, pytest, Docker Compose.

---

## File structure locked by this plan

```text
.
├── apps/
│   ├── web/
│   │   ├── app/
│   │   │   ├── (auth)/login/page.tsx
│   │   │   ├── (auth)/register/page.tsx
│   │   │   ├── auth/callback/route.ts
│   │   │   ├── dashboard/page.tsx
│   │   │   ├── api/cvs/route.ts
│   │   │   └── cvs/page.tsx
│   │   ├── lib/supabase/{client,server,proxy}.ts
│   │   ├── lib/cv/validation.ts
│   │   ├── proxy.ts
│   │   └── tests/
│   └── worker/
│       ├── jobmatch_worker/
│       │   ├── config.py
│       │   ├── db.py
│       │   ├── queue.py
│       │   ├── cv/extract.py
│       │   └── main.py
│       └── tests/
├── supabase/migrations/
├── docker-compose.yml
├── pnpm-workspace.yaml
└── Makefile
```

### Task 1: Bootstrap the monorepo and quality gates

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `apps/web/*` from `create-next-app`
- Create: `apps/worker/pyproject.toml`
- Create: `Makefile`
- Create: `.env.example`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create the web and worker projects**

Run:
```bash
pnpm create next-app@latest apps/web --ts --tailwind --eslint --app --src-dir=false --use-pnpm --import-alias='@/*'
mkdir -p apps/worker/jobmatch_worker apps/worker/tests
cd apps/worker && uv init --python 3.12
uv add pydantic pydantic-settings 'psycopg[binary,pool]' pymupdf python-docx httpx
uv add --dev pytest pytest-asyncio ruff mypy
```
Expected: Next.js app exists and `uv run python -V` reports Python 3.12.x or newer within the 3.12 line.

- [ ] **Step 2: Add root workspace commands**

Create `package.json`:
```json
{
  "name": "jobmatch-saas",
  "private": true,
  "packageManager": "pnpm@10",
  "scripts": {
    "web:dev": "pnpm --dir apps/web dev",
    "web:test": "pnpm --dir apps/web test",
    "worker:test": "cd apps/worker && uv run pytest",
    "check": "pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && cd apps/worker && uv run ruff check . && uv run mypy jobmatch_worker && uv run pytest"
  }
}
```

Create `pnpm-workspace.yaml`:
```yaml
packages:
  - apps/web
```

Add to `apps/web/package.json`:
```json
{
  "scripts": {
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  }
}
```
Then run:
```bash
cd apps/web && pnpm add @supabase/supabase-js @supabase/ssr
cd apps/web && pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom
```
Expected: dependency installation exits 0.

- [ ] **Step 3: Add a failing smoke test for each runtime**

Create `apps/web/tests/smoke.test.ts`:
```ts
import { describe, expect, it } from "vitest";

describe("web smoke", () => {
  it("has a test runner", () => expect(true).toBe(true));
});
```

Create `apps/worker/tests/test_smoke.py`:
```python
def test_worker_smoke() -> None:
    assert True
```

Run:
```bash
pnpm --dir apps/web test
cd apps/worker && uv run pytest -q
```
Expected: both suites PASS.

- [ ] **Step 4: Add environment contract and local service skeleton**

Create `.env.example`:
```dotenv
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=replace-with-local-publishable-key
SUPABASE_SERVICE_ROLE_KEY=server-only
DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
CV_BUCKET=cvs
WORKER_POLL_SECONDS=1
```

Create `docker-compose.yml`:
```yaml
services:
  worker:
    build: ./apps/worker
    env_file: .env
    command: ["uv", "run", "python", "-m", "jobmatch_worker.main"]
    restart: unless-stopped
```
Expected: no AI-provider container is added. AI providers are external cloud services configured in Plan 2.

- [ ] **Step 5: Commit**

```bash
git add package.json pnpm-workspace.yaml apps .env.example docker-compose.yml
git commit -m "chore: bootstrap job matcher monorepo"
```

### Task 2: Create Supabase user, CV, and durable work-queue schema

**Files:**
- Create: `supabase/migrations/202608160001_core_cv.sql`
- Test: `supabase/tests/core_cv.sql`

- [ ] **Step 1: Write the failing SQL assertions**

Create `supabase/tests/core_cv.sql`:
```sql
begin;
select 1 / (case when to_regclass('public.profiles') is not null then 1 else 0 end);
select 1 / (case when to_regclass('public.cvs') is not null then 1 else 0 end);
select 1 / (case when to_regclass('public.work_items') is not null then 1 else 0 end);
rollback;
```

Run before migration:
```bash
supabase db reset
supabase db test supabase/tests/core_cv.sql
```
Expected: FAIL because at least one table does not exist.

- [ ] **Step 2: Implement the schema and RLS**

Create `supabase/migrations/202608160001_core_cv.sql`:
```sql
create extension if not exists pgcrypto;

create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  locale text not null default 'id' check (locale in ('id','en')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.cvs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  original_name text not null,
  mime_type text not null check (mime_type in ('application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document')),
  storage_path text,
  retain_original boolean not null default true,
  is_active boolean not null default false,
  extraction_status text not null default 'queued' check (extraction_status in ('queued','processing','extracted','failed')),
  extracted_text text,
  extraction_error text,
  created_at timestamptz not null default now()
);

create unique index one_active_cv_per_user on public.cvs(user_id) where is_active;

create table public.work_items (
  id uuid primary key default gen_random_uuid(),
  kind text not null,
  dedupe_key text not null unique,
  payload jsonb not null,
  status text not null default 'queued' check (status in ('queued','processing','completed','failed')),
  attempts integer not null default 0,
  max_attempts integer not null default 3,
  available_at timestamptz not null default now(),
  locked_at timestamptz,
  locked_by text,
  last_error text,
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.profiles enable row level security;
alter table public.cvs enable row level security;
revoke all on public.work_items from anon, authenticated;

create policy profiles_owner_all on public.profiles
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy cvs_owner_all on public.cvs
for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

insert into storage.buckets (id, name, public)
values ('cvs','cvs',false)
on conflict (id) do update set public = false;

create policy cv_storage_owner_select on storage.objects
for select to authenticated
using (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);

create policy cv_storage_owner_insert on storage.objects
for insert to authenticated
with check (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);

create policy cv_storage_owner_delete on storage.objects
for delete to authenticated
using (bucket_id = 'cvs' and (storage.foldername(name))[1] = auth.uid()::text);
```

- [ ] **Step 3: Verify migration and RLS metadata**

Run:
```bash
supabase db reset
supabase db test supabase/tests/core_cv.sql
psql "$DATABASE_URL" -Atc "select relname, relrowsecurity from pg_class where relname in ('profiles','cvs');"
```
Expected: SQL test exits 0 and both tables report `t` for RLS.

- [ ] **Step 4: Commit**

```bash
git add supabase
git commit -m "feat: add cv storage and durable work queue schema"
```

### Task 3: Implement email/password and Google authentication

**Files:**
- Create: `apps/web/lib/supabase/client.ts`
- Create: `apps/web/lib/supabase/server.ts`
- Create: `apps/web/lib/supabase/proxy.ts`
- Create: `apps/web/proxy.ts`
- Create: `apps/web/app/(auth)/login/page.tsx`
- Create: `apps/web/app/(auth)/register/page.tsx`
- Create: `apps/web/app/auth/callback/route.ts`
- Test: `apps/web/tests/auth.test.ts`

- [ ] **Step 1: Write failing auth guard tests**

Create `apps/web/tests/auth.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { requiresAuth } from "@/lib/auth/routes";

describe("requiresAuth", () => {
  it("protects dashboard and cv routes", () => {
    expect(requiresAuth("/dashboard")).toBe(true);
    expect(requiresAuth("/cvs")).toBe(true);
    expect(requiresAuth("/login")).toBe(false);
  });
});
```
Run:
```bash
pnpm --dir apps/web test -- auth.test.ts
```
Expected: FAIL because `@/lib/auth/routes` does not exist.

- [ ] **Step 2: Implement route policy and Supabase SSR clients**

Create `apps/web/lib/auth/routes.ts`:
```ts
const protectedPrefixes = ["/dashboard", "/cvs", "/jobs", "/exports", "/settings"];
export function requiresAuth(pathname: string): boolean {
  return protectedPrefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}
```

Create `apps/web/lib/supabase/client.ts`:
```ts
import { createBrowserClient } from "@supabase/ssr";
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
  );
}
```
Create `apps/web/lib/supabase/server.ts`:
```ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
          } catch {
            // Server Components cannot always mutate cookies; proxy refresh handles it.
          }
        },
      },
    },
  );
}
```

Create `apps/web/lib/supabase/proxy.ts`:
```ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { requiresAuth } from "@/lib/auth/routes";

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    },
  );
  const { data: { user } } = await supabase.auth.getUser();
  if (!user && requiresAuth(request.nextUrl.pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  return response;
}
```

Create root `apps/web/proxy.ts`:
```ts
import type { NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/proxy";

export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
```
Do not create deprecated `middleware.ts`.

- [ ] **Step 3: Implement login/register actions and Google OAuth callback**

Create `apps/web/app/(auth)/actions.ts`:
```ts
"use server";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export async function signIn(formData: FormData) {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) redirect("/login?error=invalid_credentials");
  redirect("/dashboard");
}

export async function signUp(formData: FormData) {
  const supabase = await createClient();
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const { error } = await supabase.auth.signUp({ email, password });
  if (error) redirect("/register?error=signup_failed");
  redirect("/dashboard");
}

export async function signInWithGoogle() {
  const supabase = await createClient();
  const headerStore = await headers();
  const origin = headerStore.get("origin") ?? process.env.NEXT_PUBLIC_APP_URL!;
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo: `${origin}/auth/callback` },
  });
  if (error || !data.url) redirect("/login?error=oauth_failed");
  redirect(data.url);
}
```

Create `apps/web/app/auth/callback/route.ts`:
```ts
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  if (!code) return NextResponse.redirect(new URL("/login?error=oauth_callback", url.origin));
  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  return NextResponse.redirect(new URL(error ? "/login?error=oauth_callback" : "/dashboard", url.origin));
}
```
Wire the login/register pages to these actions with plain `<form action={...}>` controls and a Google OAuth button.

- [ ] **Step 4: Run auth unit tests and manually verify protected redirect**

Run:
```bash
pnpm --dir apps/web test -- auth.test.ts
pnpm --dir apps/web typecheck
```
Expected: PASS and TypeScript exits 0.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "feat: add Supabase authentication flows"
```

### Task 4: Implement private PDF/DOCX upload and CV list

**Files:**
- Create: `apps/web/lib/cv/validation.ts`
- Create: `apps/web/app/api/cvs/route.ts`
- Create: `apps/web/app/cvs/page.tsx`
- Test: `apps/web/tests/cv-validation.test.ts`

- [ ] **Step 1: Write failing file-validation tests**

```ts
import { describe, expect, it } from "vitest";
import { validateCvFile } from "@/lib/cv/validation";

describe("validateCvFile", () => {
  it("accepts digital PDF and DOCX MIME types", () => {
    expect(validateCvFile({ type: "application/pdf", size: 1000 })).toEqual({ ok: true });
    expect(validateCvFile({ type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document", size: 1000 })).toEqual({ ok: true });
  });
  it("rejects images and files over 10 MiB", () => {
    expect(validateCvFile({ type: "image/png", size: 1000 }).ok).toBe(false);
    expect(validateCvFile({ type: "application/pdf", size: 11 * 1024 * 1024 }).ok).toBe(false);
  });
});
```
Expected first run: FAIL because function is missing.

- [ ] **Step 2: Implement validation**

Create `apps/web/lib/cv/validation.ts`:
```ts
const allowed = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);
const MAX_BYTES = 10 * 1024 * 1024;

export function validateCvFile(file: { type: string; size: number }) {
  if (!allowed.has(file.type)) return { ok: false as const, error: "Only PDF and DOCX are supported." };
  if (file.size > MAX_BYTES) return { ok: false as const, error: "CV must be 10 MiB or smaller." };
  return { ok: true as const };
}
```

- [ ] **Step 3: Implement upload route transaction**

`POST /api/cvs` must:
1. require an authenticated Supabase user;
2. validate MIME/size;
3. insert `cvs` row;
4. upload to private path `${user.id}/${cv.id}/${safeFilename}`;
5. update `storage_path`;
6. insert a work item with `kind='extract_cv'`, `dedupe_key='extract_cv:' || cv.id`, and payload `{cv_id,user_id}`;
7. return HTTP 201 with the CV id.

If storage upload fails after row creation, delete the row so no orphan remains.

- [ ] **Step 4: Implement `/cvs` page and verify owner scoping**

The page uses the authenticated server client to select only `cvs` rows visible under RLS and displays name, status, active badge, retain-original flag, and created date.

Run:
```bash
pnpm --dir apps/web test -- cv-validation.test.ts
pnpm --dir apps/web typecheck
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "feat: add private cv upload flow"
```

### Task 5: Implement durable worker claiming and retry behavior

**Files:**
- Create: `apps/worker/jobmatch_worker/config.py`
- Create: `apps/worker/jobmatch_worker/db.py`
- Create: `apps/worker/jobmatch_worker/queue.py`
- Test: `apps/worker/tests/test_queue.py`

- [ ] **Step 1: Write failing queue-state tests**

```python
from jobmatch_worker.queue import retry_delay_seconds

def test_retry_delay_is_bounded_exponential() -> None:
    assert retry_delay_seconds(1) == 5
    assert retry_delay_seconds(2) == 10
    assert retry_delay_seconds(10) == 300
```
Expected first run: FAIL because module/function does not exist.

- [ ] **Step 2: Implement config and retry policy**

```python
# jobmatch_worker/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    worker_poll_seconds: float = 1.0
    worker_id: str = "worker-1"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

```python
# jobmatch_worker/queue.py
def retry_delay_seconds(attempt: int) -> int:
    return min(300, 5 * (2 ** max(0, attempt - 1)))
```

- [ ] **Step 3: Implement atomic claiming query**

Use one transaction with:
```sql
with candidate as (
  select id
  from public.work_items
  where status = 'queued' and available_at <= now()
  order by created_at
  for update skip locked
  limit 1
)
update public.work_items w
set status='processing', locked_at=now(), locked_by=%s, attempts=attempts+1
from candidate
where w.id=candidate.id
returning w.*;
```
On retryable failure, set `status='queued'`, clear lock fields, set `available_at = now() + delay`, and save a sanitized error. On final failure, set `status='failed'`.

- [ ] **Step 4: Run tests**

```bash
cd apps/worker && uv run pytest tests/test_queue.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/worker
git commit -m "feat: add durable postgres worker queue"
```

### Task 6: Extract text from digital PDF and DOCX, reject image-only PDFs

**Files:**
- Create: `apps/worker/jobmatch_worker/cv/extract.py`
- Create: `apps/worker/jobmatch_worker/main.py`
- Test: `apps/worker/tests/test_cv_extract.py`
- Test fixtures: `apps/worker/tests/fixtures/sample.pdf`, `sample.docx`, `image-only.pdf`

- [ ] **Step 1: Write failing extraction tests**

```python
from pathlib import Path
import pytest
from jobmatch_worker.cv.extract import UnsupportedScannedPdf, extract_cv_text

FIX = Path(__file__).parent / "fixtures"

def test_extracts_pdf_and_docx_text() -> None:
    assert "Python" in extract_cv_text(FIX / "sample.pdf")
    assert "Python" in extract_cv_text(FIX / "sample.docx")

def test_rejects_image_only_pdf() -> None:
    with pytest.raises(UnsupportedScannedPdf):
        extract_cv_text(FIX / "image-only.pdf")
```
Expected first run: FAIL.

- [ ] **Step 2: Implement extraction without OCR**

```python
from pathlib import Path
import fitz
from docx import Document

class UnsupportedScannedPdf(ValueError):
    pass

def extract_cv_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        with fitz.open(path) as doc:
            text = "\n".join(page.get_text("text") for page in doc).strip()
        if len(text) < 80:
            raise UnsupportedScannedPdf("PDF has no usable text layer; upload a digital PDF or DOCX.")
        return text
    if suffix == ".docx":
        doc = Document(path)
        text = "\n".join(p.text for p in doc.paragraphs).strip()
        if len(text) < 80:
            raise ValueError("DOCX contains too little extractable text.")
        return text
    raise ValueError("Only PDF and DOCX are supported.")
```

- [ ] **Step 3: Wire `extract_cv` work items**

`main.py` must download the private object using server credentials, call `extract_cv_text`, update `cvs.extracted_text` and `extraction_status='extracted'`, and delete the object after success when `retain_original=false`. For `UnsupportedScannedPdf`, mark the CV `failed` with the user-safe message and complete the queue item without provider retries.

- [ ] **Step 4: Run focused and full tests**

```bash
cd apps/worker && uv run pytest tests/test_cv_extract.py -q && uv run pytest -q
pnpm --dir apps/web test
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/worker
git commit -m "feat: extract digital pdf and docx cvs"
```

## Plan 1 acceptance checkpoint

Run:
```bash
pnpm --dir apps/web test
pnpm --dir apps/web typecheck
cd apps/worker && uv run ruff check . && uv run mypy jobmatch_worker && uv run pytest -q
supabase db reset
```
Expected: all commands exit 0. Manual smoke: authenticated user uploads PDF/DOCX, queue reaches `completed`, CV reaches `extracted`; image-only PDF reaches `failed` with a clear no-OCR message; another user cannot read that CV row or storage object.
