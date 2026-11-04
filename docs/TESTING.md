# Testing Guide

## Testing layers

### Unit tests

Web:

- validation;
- filtering (including discovery/result preference parity fixtures);
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

### Filter parity tests

When changing discovery preferences or result filters, keep the web and worker
contracts aligned:

- discovery preference tests live in `apps/worker/tests/test_job_preferences.py`
  and assert literal substring exclusions and unknown-metadata policy;
- result/export parity uses named synthetic cases (P1–P10, F1–F9) in
  `apps/web/tests/job-filter.test.ts`, `apps/web/tests/export-request.test.ts`,
  and `apps/worker/tests/test_export_service.py`;
- query comparison is NFC + whitespace collapse + `toLowerCase()`/`lower()` in
  both runtimes. Do not switch one side to `casefold()` or accent removal.

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

Also verify cross-user denial, latest-run dashboard scoping, and combined result
filters. Export request and history behavior remain available on the dedicated
exports page; export filter contracts are covered by API and worker tests.

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
