# Architecture

## Why this architecture

The MVP separates user-facing request/response work from long-running discovery and matching work. This avoids forcing crawling, queue processing, and scheduled jobs into the web request path while keeping infrastructure small.

## Topology

```text
                         Internet
                            |
                            v
                    +---------------+
                    |    Vercel     |
                    | Next.js SaaS  |
                    +-------+-------+
                            |
               +------------+------------+
               |                         |
               v                         v
        Supabase Auth              PostgreSQL
                                   + Storage
                                       |
                                       v
                              +------------------+
                              | Worker/Scheduler |
                              | persistent VPS   |
                              +--------+---------+
                                       |
                              +--------v---------+
                              | AI Provider      |
                              | Router           |
                              +---+--------+-----+
                                  |        |
                          +-------+--+  +--+----------+
                          | NVIDIA   |  | OpenRouter  |
                          +----------+  +-------------+
                                  \\        /
                                   \\      /
                                  Ollama Cloud
```

## Vercel responsibilities

- Next.js UI and server-side route handlers appropriate for request/response work.
- Authentication integration.
- Dashboard, CV management, search controls, tracking, and export UX.
- Authenticated API/BFF endpoints.
- Queue/search/export trigger requests.

Vercel is not the long-running crawler or local model host.

## Supabase responsibilities

- Email/password and Google OAuth identity integration.
- PostgreSQL domain data.
- Row Level Security for user-owned data.
- Private object storage for CVs and generated exports.
- Durable work queue tables used by the worker.

## Worker/Scheduler responsibilities

- Extract text from digital PDF/DOCX files.
- Consume durable queue items.
- Discover jobs through modular connectors.
- Fetch permitted job pages.
- Normalize, canonicalize, and deduplicate jobs.
- Extract/cache job requirements.
- Orchestrate hybrid matching and recommendations.
- Run daily scheduled discovery.
- Record privacy-safe operational metadata.

The worker does not host Ollama in the MVP.

## AI provider boundary

Every generative model call passes through an internal provider-neutral router.

```text
Business operation
    |
    v
AiRouter.generate_structured(...)
    |
    +-> NVIDIA NIM
    +-> OpenRouter
    +-> Ollama Cloud
```

Provider-specific HTTP formats stay inside adapter modules. Business code sees one result contract.

## Data reuse

Expensive transformations are cached:

```text
CV file -> extracted text -> candidate profile
                         reused across jobs

Canonical job description -> structured requirements
                           reused across users/runs
```

This reduces latency, API usage, and unnecessary exposure of personal data.

## Canonical job versus user match

A canonical job is shared data. A match is user-specific.

```text
Canonical Job
  +-> User A match: 92
  +-> User B match: 71
  +-> User C match: 84
```

Do not duplicate the canonical job row merely because multiple users matched it.

## Failure isolation

- One failed source must not fail the whole discovery run.
- One failed job analysis must not discard successful matches.
- Retryable provider errors can fall back to the next provider.
- Domain/authorization errors do not trigger provider fallback.
- Partially successful batches use `PARTIAL` rather than discarding useful results.

## Scale path

The initial worker is one logical service on one VPS. Later, crawler, scheduler, matching, or specialized workers may be split while preserving database/API contracts. Such scaling is future work, not MVP scope.
