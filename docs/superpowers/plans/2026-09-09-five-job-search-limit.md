# Five-Job Search Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Limit every manual and daily discovery run to five persisted and processed distinct jobs.

**Architecture:** Apply one named product limit after normalization and deduplication in the discovery handler. Pass only the selected five jobs to canonical persistence, run linkage, provenance, requirement extraction, and matching while retaining source totals and true duplicate counts.

**Tech Stack:** Python 3.12, asyncio, psycopg, pytest, Ruff, mypy.

---

### Task 1: Enforce the five-job run limit

**Files:**
- Modify: `apps/worker/tests/test_discovery_handler.py`
- Modify: `apps/worker/jobmatch_worker/handlers/discovery.py`

- [ ] **Step 1: Write the failing discovery regression**

Add a test that sends seven distinct jobs through one connector and inspects the
existing production-shaped connection fake:

```python
@pytest.mark.asyncio
async def test_discovery_run_persists_at_most_five_distinct_jobs() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-limited",
        "status": "queued",
        "region": "global",
        "target_roles": ["Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    jobs = [
        _job(
            source_key="greenhouse",
            url=f"https://jobs.example.com/engineer-{number}",
            title=f"Engineer {number}",
        )
        for number in range(1, 8)
    ]
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {"id": "item-limited", "payload": {"search_run_id": "run-limited"}},
        SimpleNamespace(requirement_extraction_enabled=True, max_attempts=3),
        connectors={"greenhouse": _Connector("greenhouse", jobs)},
    )

    job_inserts = [
        params
        for query, params in connection.executed
        if "insert into public.jobs" in query.lower()
    ]
    provenance = [
        params
        for query, params in connection.executed
        if "insert into public.job_provenance" in query.lower()
    ]
    requirement_items = [
        params
        for query, params in connection.executed
        if "insert into public.work_items" in query.lower()
        and params[0] == "extract_job_requirements"
    ]
    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    final_update = next(params for params in run_updates if params[0] == "processing")

    assert [params[1] for params in job_inserts] == [f"Engineer {number}" for number in range(1, 6)]
    assert len(provenance) == 5
    assert len(requirement_items) == 5
    assert final_update[1:5] == (7, 5, 0, 0)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
cd apps/worker
uv run pytest tests/test_discovery_handler.py::test_discovery_run_persists_at_most_five_distinct_jobs -q
```

Expected: fail because seven job inserts, provenance rows, and requirement items
are produced and `normalized_count` is seven.

- [ ] **Step 3: Implement the minimum product limit**

Add the named constant beside the existing discovery safety limits:

```python
_MAX_JOBS_PER_RUN = 5
```

Apply it after true deduplication and before persistence:

```python
kept, duplicate_count = dedupe_jobs(normalized)
kept = kept[:_MAX_JOBS_PER_RUN]
upsert_result = await upsert_jobs(conn, search_run_id=run_id, jobs=kept)
```

Do not add omitted valid jobs to `duplicate_count`.

- [ ] **Step 4: Verify GREEN and broader worker gates**

Run:

```bash
cd apps/worker
uv run pytest tests/test_discovery_handler.py -q
uv run pytest -q
uv run ruff check .
uv run mypy jobmatch_worker
cd ../..
git diff --check
```

Expected: focused and full worker suites pass, the optional live AI test remains
skipped, Ruff and mypy pass, and Git reports no whitespace errors.

- [ ] **Step 5: Commit the behavior and regression**

```bash
git add apps/worker/tests/test_discovery_handler.py apps/worker/jobmatch_worker/handlers/discovery.py
git diff --cached --check
git commit -m "feat: limit each job search to five results"
```

### Task 2: Reconcile product and verification records

**Files:**
- Modify: `implementaitons_plan.md`
- Modify: `docs/VERIFICATION-2026-09-08.md`
- Modify: `docs/superpowers/specs/2026-09-06-critical-high-audit-remediation-design.md`

- [ ] **Step 1: Mark the former unlimited-run statement as superseded**

Add a dated note to the older remediation design that the user-approved
five-job MVP rule in `2026-09-09-five-job-search-limit-design.md` supersedes its
instruction to remove the output cap.

- [ ] **Step 2: Record the implementation outcome**

Add Task 12 to `implementaitons_plan.md` with the exact commit and fresh test
counts. Append the same focused and broad verification evidence to
`docs/VERIFICATION-2026-09-08.md` without rewriting its historical results.

- [ ] **Step 3: Review and commit documentation**

Run:

```bash
git diff --check
git status --short
git diff --stat
```

Confirm that ignored environment files and the pre-existing untracked
`docs/PROJECT_ANALYSIS_REPORT.md` are not staged, then commit:

```bash
git add implementaitons_plan.md docs/VERIFICATION-2026-09-08.md docs/superpowers/specs/2026-09-06-critical-high-audit-remediation-design.md
git diff --cached --check
git commit -m "docs: record five-job search limit"
```

- [ ] **Step 4: Push the reviewed commits**

```bash
git push origin codex/fix-post-merge-acceptance
```

Expected: PR #3 updates with the design, implementation, regression, and fresh
verification evidence.
