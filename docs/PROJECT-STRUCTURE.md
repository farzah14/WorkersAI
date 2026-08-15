# Project Structure Reference

The structure below is the intended repository shape as the six plans are implemented.

```text
.
|-- AGENTS.md
|-- README.md
|-- CONTRIBUTING.md
|-- .env.example
|-- apps/
|   |-- web/
|   |   |-- app/
|   |   |-- lib/
|   |   |-- tests/
|   |   `-- e2e/
|   `-- worker/
|       |-- jobmatch_worker/
|       |   |-- ai/
|       |   |-- cv/
|       |   |-- discovery/
|       |   |-- jobs/
|       |   |-- matching/
|       |   |-- profiles/
|       |   `-- handlers/
|       `-- tests/
|-- supabase/
|   |-- migrations/
|   `-- tests/
|-- infra/
|   `-- worker/
|-- scripts/
|-- docs/
|   |-- README.md
|   |-- ARCHITECTURE.md
|   |-- DEVELOPMENT.md
|   |-- AI-PROVIDERS.md
|   |-- TESTING.md
|   |-- SECURITY.md
|   |-- DEPLOYMENT.md
|   |-- PROJECT-STRUCTURE.md
|   |-- DECISIONS.md
|   `-- superpowers/
|       |-- specs/
|       `-- plans/
`-- compose.production.yml
```

## `apps/web`

Owns user-facing and request/response concerns:

- authentication UI/callback;
- CV management UI/API;
- profile review;
- search controls;
- dashboard/match details;
- job tracking;
- export triggers/download UX;
- bilingual UI.

Server-only route handlers may enqueue durable background work. They should not perform long crawling/matching loops in the request path.

## `apps/worker`

Owns durable/asynchronous processing:

- queue claiming/retries;
- CV text extraction;
- AI provider adapters/router;
- profile extraction;
- job discovery connectors;
- canonicalization/deduplication;
- requirement extraction/cache;
- matching/recommendation orchestration;
- scheduler;
- privacy-safe metrics.

## `supabase`

Owns:

- schema migrations;
- constraints/indexes;
- RLS policies;
- SQL regression tests.

## `infra/worker`

Contains the production worker image definition. There is intentionally no `infra/ollama` directory in the approved MVP architecture.

## `docs/superpowers`

Contains the approved design and executable implementation plans. Treat these as controlled planning artifacts; do not rewrite them casually while implementing unrelated changes.

## Module boundary rule

Files should be organized around cohesive responsibilities. Provider/source-specific translation belongs in adapters/connectors so business logic remains provider-neutral.
