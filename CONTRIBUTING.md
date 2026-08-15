# Contributing

## Before coding

1. Read `AGENTS.md`.
2. Read the approved design spec.
3. Read `docs/superpowers/plans/README.md`.
4. Work only on the current milestone unless the user explicitly changes scope.
5. Create a feature branch or isolated worktree.

## Branching

Do not implement directly on `master`/`main` without explicit approval.

Example:

```bat
git switch -c feat/plan-1-foundation
```

## TDD workflow

For behavior changes:

1. Add the failing test.
2. Run it and confirm the intended failure.
3. Implement the minimum behavior.
4. Re-run the focused test.
5. Run the affected test suite.
6. Run lint/type checks.
7. Commit.

## Commit style

Examples:

```text
chore: bootstrap job matcher monorepo
feat: add private cv upload
feat: add configurable ai fallback router
fix: prevent duplicate canonical jobs
test: add matching golden regression case
docs: clarify ollama cloud configuration
ops: containerize worker and scheduler
```

Keep unrelated changes out of the same commit.

## Pull request checklist

- [ ] Change matches the approved MVP scope.
- [ ] Tests demonstrate the behavior.
- [ ] Web typecheck/lint pass when web code changed.
- [ ] Worker ruff/mypy/pytest pass when worker code changed.
- [ ] Supabase migration/RLS tests pass when schema changed.
- [ ] No raw CV text, API key, token, service-role key, or signed URL is committed/logged.
- [ ] Documentation is updated when contracts/configuration changed.
- [ ] `git diff --check` is clean.

## Database changes

- Add a new migration for shared/deployed schema changes.
- Never weaken RLS merely to make a test pass.
- Derive ownership from authenticated server context.
- Do not accept another user's resource owner ID from client input.

## External providers and job sources

- Keep provider-specific behavior behind adapters/connectors.
- Do not scrape a site simply because HTML is publicly reachable; use approved/documented/permitted access methods.
- Do not make a live external provider call in ordinary unit tests.
- Gate live integration tests behind explicit environment flags.

## Security reports

Do not put secrets, real CVs, or exploit payloads containing private user data in public issues. Use a private project channel for sensitive security findings.
