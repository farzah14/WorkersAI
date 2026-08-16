# Deployment Guide

## Production topology

```text
Vercel
  - Next.js web/API

Supabase
  - Auth
  - PostgreSQL
  - private Storage

One persistent VPS
  - Python worker
  - scheduler

External AI
  - NVIDIA NIM
  - OpenRouter
  - Ollama Cloud
```

There is no local Ollama service in production.

## 1. Supabase

Create/configure:

- Auth providers: email/password + Google OAuth.
- PostgreSQL database.
- private `cvs` bucket.
- private export bucket when Plan 5 adds exports.
- all repository migrations in order.
- RLS policies and SQL assertions.

Keep service-role credentials server-side only.

## 2. Vercel

Deploy `apps/web` after the application exists.

Configure only values needed by the web runtime. Public browser-safe values may use `NEXT_PUBLIC_*`; server secrets must remain server-only Vercel environment variables.

Do not expose provider keys to client bundles.

## 3. Worker VPS

The VPS runs persistent background processes that are unsuitable for the user-facing request path:

- queue worker;
- daily scheduler.

Production Compose contains those services only.

Conceptual shape:

```yaml
services:
  worker:
    build: ...
    env_file: .env.production
    restart: unless-stopped
  scheduler:
    build: ...
    env_file: .env.production
    command: ["uv", "run", "python", "-m", "jobmatch_worker.scheduler"]
    restart: unless-stopped
```

Do not add:

- `ollama` service;
- Ollama model volume;
- GPU runtime;
- `OLLAMA_HOST=http://ollama:11434`;
- local model-pull init container.

## 4. Production environment

The VPS `.env.production` is not committed. It contains the database/storage credentials required by the worker and:

```dotenv
AI_PROVIDER_ORDER=nvidia,ollama,openrouter
NVIDIA_API_KEY=...
NVIDIA_BASE_URL=...
NVIDIA_MODEL=...
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
OLLAMA_API_KEY=...
OLLAMA_BASE_URL=https://ollama.com/api
OLLAMA_MODEL=...
OLLAMA_EMBED_MODEL=
```

## 5. Provider behavior

Provider availability and free quotas can change. Deployment configuration must therefore allow model IDs and provider order to change without rewriting business logic.

A provider outage should degrade through the configured router instead of requiring a redeploy, where configuration management permits.

## 6. Production verification

Before release:

- all milestone tests pass;
- database migrations/RLS checks pass;
- Playwright MVP acceptance passes against a staging environment;
- Compose configuration validates;
- worker can connect to Postgres;
- private buckets are not publicly readable;
- no secret appears in client bundles/logs;
- provider contract smoke checks are run only with controlled test data.

## 7. Operations

Monitor:

- work queue depth and failures;
- search-run partial/failure rate;
- source connector health;
- provider latency/fallback count;
- job normalization/deduplication counts;
- matching completion/failure counts;
- scheduler-created runs.

Do not log raw CV content for convenience.

## Rollback principle

Application/container rollback must not depend on reversing destructive database changes. Prefer backward-compatible migrations and roll forward with a corrective migration when schema changes have already been applied.
