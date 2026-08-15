.PHONY: web-dev web-test web-lint web-typecheck worker-test worker-lint worker-typecheck check supabase-start supabase-reset

web-dev:
	pnpm --dir apps/web dev

web-test:
	pnpm --dir apps/web test

web-lint:
	pnpm --dir apps/web lint

web-typecheck:
	pnpm --dir apps/web typecheck

worker-test:
	cd apps/worker && uv run pytest

worker-lint:
	cd apps/worker && uv run ruff check .

worker-typecheck:
	cd apps/worker && uv run mypy jobmatch_worker

check:
	pnpm --dir apps/web lint
	pnpm --dir apps/web typecheck
	cd apps/worker && uv run ruff check . && uv run mypy jobmatch_worker && uv run pytest

supabase-start:
	pnpm exec supabase start

supabase-reset:
	pnpm exec supabase db reset