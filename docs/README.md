# Documentation Map

The repository uses a Diataxis-style documentation split.

## Tutorial / onboarding

- `DEVELOPMENT.md` - set up the project and execute implementation plans from Windows CMD.

## How-to guides

- `TESTING.md` - run focused, integration, E2E, and golden tests.
- `DEPLOYMENT.md` - deploy web, data services, and worker/scheduler.
- `CONTRIBUTING.md` at repository root - branch, test, commit, and review workflow.

## Reference

- `AGENTS.md` at repository root - non-negotiable coding-agent rules.
- `AI-PROVIDERS.md` - provider contract, configuration, retries, and fallback.
- `SECURITY.md` - security requirements and prohibited data handling.
- `PROJECT-STRUCTURE.md` - intended directories and responsibilities.
- `.env.example` at repository root - environment variable contract.

## Explanation

- `ARCHITECTURE.md` - why the hybrid modular design is split across Vercel, Supabase, and a persistent worker.
- `DECISIONS.md` - locked product and infrastructure decisions.

## Product and implementation source material

- `superpowers/specs/2026-08-16-ai-job-matcher-saas-design.md` - approved product design.
- `superpowers/plans/README.md` - implementation roadmap.
- `superpowers/plans/*.md` - executable milestone plans.
