# Development Guide - Windows CMD

## Audience

This guide is for the primary developer running the project from Windows CMD. Linux-only commands are reserved for the production VPS sections.

## Goal

Prepare the toolchain, clone/open the repository, create a feature branch, configure local secrets, and execute the implementation plans in order.

## 1. Check the toolchain

Run in CMD:

```bat
node -v
npm -v
python --version
git --version
where pnpm
where uv
where docker
```

Target baseline:

- Node.js compatible with Next.js 16.
- pnpm 10.
- Python 3.12+.
- `uv` available for Python dependency/environment management.
- Git.
- Docker Desktop for local containers/Supabase workflows when required.

If pnpm is missing and Corepack is available:

```bat
corepack enable
corepack prepare pnpm@10 --activate
pnpm -v
```

## 2. Open the repository

```bat
cd C:\path\to\jobmatch-saas
git status
git branch --show-current
```

Read `AGENTS.md` before changing files.

## 3. Create an implementation branch

```bat
git switch -c feat/plan-1-foundation
```

Use a separate branch/worktree rather than implementing on `master`.

## 4. Configure local environment

After `.env.example` exists:

```bat
copy .env.example .env
```

Edit `.env` locally. Do not paste real secrets into chat, commit history, screenshots, or issue text.

The MVP uses cloud AI providers:

```text
NVIDIA NIM -> OpenRouter -> Ollama Cloud
```

There is no local Ollama setup step.

## 5. Execute plans in order

```text
Plan 1: foundation + auth + CV ingestion
Plan 2: AI router + candidate profile
Plan 3: job discovery
Plan 4: matching + recommendations
Plan 5: dashboard + tracking + export
Plan 6: daily discovery + production hardening
```

The current plan contains the exact files, tests, and expected checkpoints.

## 6. Typical web commands after Plan 1 bootstrap

```bat
pnpm --dir apps\web dev
pnpm --dir apps\web test
pnpm --dir apps\web typecheck
pnpm --dir apps\web lint
```

## 7. Typical worker commands after Plan 1 bootstrap

```bat
cd apps\worker
uv run pytest -q
uv run ruff check .
uv run mypy jobmatch_worker
cd ..\..
```

## 8. Supabase commands

The implementation plan may use a project-local Supabase CLI. Prefer invoking the version pinned by the repository rather than relying on an arbitrary global version.

Typical flow after Supabase is configured:

```bat
pnpm exec supabase start
pnpm exec supabase db reset
pnpm exec supabase status
```

For SQL assertion scripts, use the PostgreSQL client available in your selected local setup. Keep `DATABASE_URL` in `.env`; do not commit it if it contains non-local credentials.

## 9. Docker checks

```bat
docker --version
docker compose version
```

Production Compose contains the Python worker and scheduler only. It must not contain an Ollama service.

## 10. End-of-task verification

Run the checks relevant to the files you changed. Before a milestone checkpoint, run the full affected suite and:

```bat
git status
git diff --check
```

Do not move to the next plan with failing acceptance tests.

## Troubleshooting principle

When a command fails:

1. Copy the complete command and error output.
2. Do not randomly change dependency versions.
3. Check the active implementation plan and `AGENTS.md`.
4. Resolve the first failing prerequisite before continuing.
