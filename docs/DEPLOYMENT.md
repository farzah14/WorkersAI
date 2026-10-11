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
  - 9Router OpenAI-compatible gateway
```

The worker talks to 9Router through `NINEROUTER_BASE_URL`. The default
`http://localhost:20128/v1` is suitable only when the gateway is reachable from
the worker container at that address; set a network-reachable production URL
otherwise. There is no local Ollama service or port `11434` dependency in
production.

## 1. Supabase

Create/configure:

- Auth providers: email/password + Google OAuth.
- PostgreSQL database.
- private `cvs` bucket.
- private export bucket when Plan 5 adds exports.
- all repository migrations in order.
- RLS policies and SQL assertions.

Run the pgTAP suites against the linked hosted project from a local psql session (the CLI `db test` runner installs pgtap outside the test session search path on hosted):

```bat
set PGUSER=postgres.<project-ref>
set PGPASSWORD=<db-password>
set PGHOST=aws-0-<region>.pooler.supabase.com
psql -A -t -v ON_ERROR_STOP=1 -f supabase\tests\core_cv.sql
```

Expect zero `not ok` lines. Tests are scoped to fixture data and may be rerun on a database that already contains real usage rows.

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
AI_PROVIDER_ORDER=9router
AI_TIMEOUT_SECONDS=30
NINEROUTER_BASE_URL=http://localhost:20128/v1
NINEROUTER_API_KEY=...
NINEROUTER_MODEL=...
NINEROUTER_EMBED_MODEL=
EXPORTS_BUCKET=exports
DAILY_DISCOVERY_HOUR_JAKARTA=7
REQUIREMENT_EXTRACTION_ENABLED=true
```

`NINEROUTER_MODEL` is required when `9router` is in the provider order. The
API key is server-only and may be empty only for a keyless local gateway.
The worker also accepts the legacy `EXPORT_BUCKET` and
`DAILY_DISCOVERY_HOUR_ASIA_JAKARTA` names, but canonical names take precedence.

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
