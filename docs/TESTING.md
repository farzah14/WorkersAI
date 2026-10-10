# Testing Guide

## Testing layers

### Unit tests

Web:

- validation;
- filtering;
- display bucketing;
- safe client/server schemas.

Worker:

- CV validation/extraction helpers;
- canonicalization/deduplication;
- score calculation;
- requirement weighting;
- AI error classification/router behavior;
- semantic fallback;
- recommendation guardrails.

### Database and RLS tests

Verify:

- required tables/indexes/constraints exist;
- one active CV per user;
- cross-user access is denied;
- private user-owned data is protected;
- queue idempotency constraints work;
- deletion cascades behave as intended.

### Integration tests

Cover:

- CV -> extracted text -> candidate profile;
- source payload -> normalized canonical job;
- job description -> cached requirements;
- candidate profile + requirements -> match result;
- AI router retry/fallback;
- search run -> persisted ranked results.

### End-to-end tests

Core Playwright journey:

```text
Register/Login
-> Upload CV
-> Review Profile
-> Configure Indonesia/Global search
-> Find Jobs
-> View Match
-> Save / Applied / Ignore
-> Export
```

Also verify cross-user denial.

### Golden dataset

Maintain deterministic candidate/job fixtures representing high, medium, and low broad match outcomes. Run golden tests when changing:

- score weights;
- prompts;
- requirement extraction;
- semantic logic;
- AI providers/models;
- critical-gap logic.

Golden tests detect regressions; they do not claim an objective universal hiring truth.

## Windows CMD commands

After bootstrap, typical web verification:

```bat
pnpm --dir apps\web test
pnpm --dir apps\web typecheck
pnpm --dir apps\web lint
```

Worker:

```bat
cd apps\worker
uv run ruff check .
uv run mypy jobmatch_worker
uv run pytest -q
cd ..\..
```

E2E:

```bat
pnpm --dir apps\web exec playwright test
```

Database checks depend on the project-local Supabase/Postgres setup established in Plan 1.

## External API tests

Ordinary CI must not require paid/live provider calls.

Use deterministic HTTP mocks for:

- NVIDIA responses/errors;
- OpenRouter responses/errors;
- Ollama Cloud responses/errors;
- job discovery source responses.

Live checks are opt-in:

```dotenv
ENABLE_LIVE_AI_TESTS=1
ENABLE_LIVE_JOB_SOURCE_TESTS=1
```

Never make live provider tests a normal merge gate while free quotas/availability are variable.

## Verification before completion

Before claiming a task complete, run fresh verification for the affected area. Before a milestone checkpoint, run the complete milestone acceptance suite and:

```bat
git diff --check
```

A passing unit test is not proof that typecheck, RLS, E2E, or production configuration is correct.
