# AI Job Matcher MVP Implementation Plan Set

The approved MVP specification spans independent subsystems, so implementation is split into six executable plans. Execute them in order because each plan produces a working milestone used by the next.

1. `2026-08-16-platform-foundation-and-cv-ingestion.md` — repository, Supabase, authentication, private CV upload, durable DB queue, PDF/DOCX text extraction.
2. `2026-08-16-ai-router-and-candidate-profile.md` — NVIDIA/OpenRouter/Ollama adapters, fallback/circuit breaker, schema-valid candidate profile extraction, review/edit/active CV.
3. `2026-08-16-job-discovery-pipeline.md` — search preferences, Brave web discovery, Greenhouse/Lever connectors, permitted page fetching, normalization, canonicalization, deduplication.
4. `2026-08-16-matching-and-recommendations.md` — requirement extraction/cache, deterministic + semantic scoring, critical gaps, verdicts, recommendations, golden dataset.
5. `2026-08-16-dashboard-tracking-and-exports.md` — ranked dashboard, filters/buckets, Saved/Applied/Ignored tracking, bilingual UI, Excel/PDF exports.
6. `2026-08-16-daily-discovery-and-production-hardening.md` — scheduler, idempotency, rate limits, job freshness, observability, deletion/privacy flows, Docker/VPS deployment, E2E acceptance suite.

## Locked implementation stack

- Web: Next.js 16 App Router + TypeScript + Tailwind CSS, deployed to Vercel.
- Identity/data/storage: Supabase Auth + PostgreSQL + private Storage with RLS.
- Worker: Python 3.12+, asyncio/psycopg, Pydantic, HTTPX, PyMuPDF, python-docx.
- Queue: PostgreSQL-backed `work_items` table using `FOR UPDATE SKIP LOCKED`; no Redis for MVP.
- AI: configurable NVIDIA NIM -> OpenRouter -> Ollama Cloud fallback; every structured response is validated by Pydantic.
- Ollama: cloud API only through `OLLAMA_API_KEY` and `OLLAMA_BASE_URL=https://ollama.com/api`; model identifiers are configuration, not hardcoded defaults.
- Semantic similarity: optional Ollama Cloud embedding model when configured, with deterministic lexical degradation when cloud embeddings are unavailable.
- Job discovery baseline: Brave Search API, Greenhouse Job Board API, Lever Postings API, and permitted public career-page fetches.
- Testing: Vitest + Playwright for web; pytest for worker; SQL/RLS integration checks against local Supabase.
- Deployment: Vercel + Supabase + one Docker Compose VPS hosting worker/scheduler only; all three AI providers are external cloud services.

## Execution policy

Use TDD inside every plan: failing test, verify failure, minimal implementation, verify pass, commit. Do not begin a later plan while an earlier plan has failing acceptance tests.

## Specification coverage matrix

| Approved requirement | Implemented by plan |
|---|---|
| Email/password + Google auth | 1 |
| PDF/DOCX only, no OCR; private retention choice | 1 |
| Three-provider fallback + circuit breaker | 2 |
| Editable candidate profile + one active CV | 2 |
| Indonesia/Global search profile | 3 |
| Hybrid discovery + source isolation + dedupe | 3 |
| Cached requirements + hybrid scoring | 4 |
| Six score dimensions + critical gaps + recommendations | 4 |
| Four dashboard buckets + original links | 5 |
| Saved/Applied/Ignored tracking | 5 |
| Excel/PDF filter-aware export | 5 |
| Bahasa Indonesia/English | 5 |
| Daily discovery | 6 |
| Rate limiting, freshness, privacy deletion, observability | 6 |
| Vercel + Supabase + one VPS worker/scheduler plus cloud AI providers | 1, 2, and 6 |
| Cross-user isolation + full E2E acceptance | 1, 5, and 6 |
