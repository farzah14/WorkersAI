# AI Job Matcher

AI Job Matcher is a job-seeker-first SaaS that turns a digital PDF/DOCX CV into an editable candidate profile, automatically discovers relevant jobs, computes explainable match scores, recommends next actions, tracks applications, and exports filtered results to Excel or PDF.

## MVP flow

```text
Register / Login
    -> Upload PDF/DOCX CV
    -> Extract structured candidate profile
    -> User reviews/edits profile
    -> Configure Indonesia or Global search
    -> Discover / normalize / deduplicate jobs
    -> Extract requirements
    -> Hybrid matching
    -> Rank + explain + recommend
    -> Save / Applied / Ignore
    -> Export Excel / PDF
```

## Architecture

```text
Browser
  |
  v
Vercel / Next.js
  |
  +---- Supabase Auth
  +---- PostgreSQL + private Storage
  |
  v
Worker / Scheduler VPS
  |
  +---- job discovery / crawling
  +---- CV processing
  +---- normalization / deduplication
  +---- matching orchestration
  |
  v
AI Provider Router
  +---- NVIDIA NIM
  +---- OpenRouter
  +---- Ollama Cloud
```

Ollama is cloud-only in the MVP. The VPS does not host an Ollama daemon or local AI model.

## Repository documentation

Start here:

- `AGENTS.md` - rules for coding agents and contributors.
- `docs/README.md` - documentation map.
- `docs/ARCHITECTURE.md` - system boundaries and data flow.
- `docs/DEVELOPMENT.md` - Windows CMD development workflow.
- `docs/AI-PROVIDERS.md` - provider contract and fallback rules.
- `docs/SECURITY.md` - PII, RLS, secret, and prompt-injection requirements.
- `docs/TESTING.md` - test strategy and verification commands.
- `docs/DEPLOYMENT.md` - Vercel/Supabase/VPS topology.
- `docs/DECISIONS.md` - locked architecture decisions.
- `docs/PROJECT-STRUCTURE.md` - intended module ownership.
- `CONTRIBUTING.md` - contribution workflow.

Product source of truth:

- `docs/superpowers/specs/2026-08-16-ai-job-matcher-saas-design.md`

Implementation sequence:

- `docs/superpowers/plans/README.md`

## Implementation order

1. Platform foundation and CV ingestion.
2. AI router and candidate profile.
3. Job discovery pipeline.
4. Matching and recommendations.
5. Dashboard, tracking, and exports.
6. Daily discovery and production hardening.

Do not skip forward while an earlier milestone has failing acceptance checks.

## Locked stack

- Next.js 16 + TypeScript + Tailwind CSS.
- Vercel.
- Supabase Auth/PostgreSQL/private Storage.
- Python 3.12+ worker.
- PostgreSQL durable queue; no Redis in the MVP.
- NVIDIA NIM + OpenRouter + Ollama Cloud fallback.
- Vitest + Playwright + pytest + SQL/RLS tests.

## Local development

The primary developer workflow is Windows CMD. Follow `docs/DEVELOPMENT.md` before executing Plan 1.

Never commit real API keys or real user CV data.
