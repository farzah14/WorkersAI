# WorkersAI Bug Research & Remediation Plan

## Context

A full-stack audit of the WorkersAI repository (`apps/worker`, `apps/web`, `supabase/migrations`, `scripts/`, and `docker-compose.yml`) identified 9 concrete runtime bugs, data-consistency defects, API contract mismatches, and infrastructure/test-harness errors. This plan specifies the root cause and exact code solution for each problem so all fixes can be applied and verified cleanly without altering MVP scope.

## Approach

### 1. Fix Premature Search Run Finalization on Retryable Worker Failures

- **Problem**:
  - In `apps/worker/jobmatch_worker/handlers/matching.py`, `handle_match_job` (lines 336–343) catches transient exceptions, calls `retry_item(conn, item_id, str(exc), attempt)` when `attempt < settings.max_attempts`, and then unconditionally calls `await _complete_run_if_terminal(conn, str(run_id), current_item_id=item_id)`.
  - Because `_PENDING_ITEMS_SQL` (line 53) excludes `current_item_id` via `where (%s::uuid is null or id <> %s::uuid)`, if the retrying `match_job` item is the last remaining item in the batch, `pending` evaluates to `0` while `failed` is `0`. `_complete_run_if_terminal` prematurely marks `public.job_search_runs` as `completed` (or `partial`/`failed`) with `completed_at = now()` while the item is still queued for retry.
  - Similarly, `handle_extract_job_requirements` (lines 247–254) calls `await _complete_runs_for_job_if_terminal(conn, str(job_id))` even after rescheduling the item via `retry_item`.
- **Solution**:
  - Edit `apps/worker/jobmatch_worker/handlers/matching.py` in `handle_extract_job_requirements` (lines 247–254) and `handle_match_job` (lines 336–343) so `_complete_runs_for_job_if_terminal` and `_complete_run_if_terminal` execute only in the terminal failure branch (`if attempt >= settings.max_attempts:`), never in the `else: await retry_item(...)` branch:
    ```python
    except Exception as exc:  # noqa: BLE001 - heterogeneous transient failures
        await conn.rollback()
        attempt = int(item.get("attempts") or 0)
        if attempt >= settings.max_attempts:
            await fail_item(conn, item_id, _failure_message("job match failed", exc))
            await _complete_run_if_terminal(conn, str(run_id), current_item_id=item_id)
        else:
            await retry_item(conn, item_id, str(exc), attempt)
    ```
  - Add regression test `test_match_job_handler_retry_does_not_complete_run` in `apps/worker/tests/test_matching_handler.py` verifying that when `handle_match_job` raises `RetryableAiError` with `attempts=1` (`< max_attempts=3`) and `pending=0`, `work_items` is updated to `queued` and no `update public.job_search_runs` statement is executed.

### 2. Fix CV Original File Deletion Verification and Table-Based DOCX Extraction

- **Problem**:
  - **Unverified Storage Deletion**: In `apps/worker/jobmatch_worker/main.py` (`handle_extract_cv`, lines 120–123), when `not cv["retain_original"]`, `await client.delete(f"/object/{settings.cv_bucket}/{storage_path}")` ignores the HTTP status code. If Supabase Storage fails (e.g., HTTP 500/503), the worker still sets `storage_path = None` in `public.cvs`, leaving the private CV object orphaned in Storage.
  - **DOCX Table Text Ignored & Retried Pointlessly**: In `apps/worker/jobmatch_worker/cv/extract.py` (`_from_docx`, lines 24–30), only top-level `doc.paragraphs` are read. CVs formatted inside Word tables (`doc.tables`) produce `< 80` characters and fail with `ValueError("DOCX contains no readable text")`. Furthermore, `handle_extract_cv` (`apps/worker/jobmatch_worker/main.py:128`) only catches `UnsupportedScannedPdf` as a non-retryable failure; `ValueError` from unreadable DOCX files triggers 3 queue retries before marking the CV failed.
- **Solution**:
  - In `apps/worker/jobmatch_worker/cv/extract.py`, update `_from_docx(path: Path) -> str` to collect paragraph text from both `doc.paragraphs` and unique cells across `doc.tables`:
    ```python
    def _from_docx(path: Path) -> str:
        doc = Document(str(path))
        parts: list[str] = [p.text for p in doc.paragraphs if p.text]
        seen_cells: set[int] = set()
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell_id = id(cell._tc)
                    if cell_id in seen_cells:
                        continue
                    seen_cells.add(cell_id)
                    for paragraph in cell.paragraphs:
                        if paragraph.text:
                            parts.append(paragraph.text)
        text = "\n".join(parts)
        if len(text.strip()) < MIN_TEXT_LENGTH:
            raise ValueError("DOCX contains no readable text")
        return text
    ```
  - In `apps/worker/jobmatch_worker/main.py`, add helper `_delete_cv(client: httpx.AsyncClient, bucket: str, path: str) -> None` that calls `response = await client.delete(f"/object/{bucket}/{path}")` and invokes `response.raise_for_status()` when `response is not None and getattr(response, "status_code", 200) != 404`. Call `_delete_cv(client, settings.cv_bucket, storage_path)` in `handle_extract_cv`, and widen `except UnsupportedScannedPdf as exc:` (line 128) to `except (UnsupportedScannedPdf, ValueError) as exc:`.
  - Add unit tests in `apps/worker/tests/test_extract.py` (table-only DOCX extraction) and `apps/worker/tests/test_profile_extract.py` (unreadable DOCX fails immediately without retry).

### 3. Fix Worker Export Retry Idempotency, PDF URL Quote Escaping, and Empty Excel AutoFilter

- **Problem**:
  - **Storage Upload Conflict on Retry**: In `apps/worker/jobmatch_worker/exports/service.py` (`_upload_report`, lines 220–225), `client.post(f"/object/{settings.exports_bucket}/{path}", ...)` omits `"x-upsert": "true"`. If an export work item retries after uploading the file (e.g., transient DB error before `_mark_status`), Supabase Storage returns HTTP 400 (`Duplicate`), failing the retry.
  - **Unescaped Quotes in PDF `<link>`**: In `apps/worker/jobmatch_worker/exports/pdf.py` (`_link`, lines 27–28), `escape(url)` escapes `&`, `<`, `>` but not `"` or `'`, causing ReportLab `Paragraph` XML parsing to raise an exception if `original_url` contains `"`.
  - **Single-Row Excel AutoFilter**: In `apps/worker/jobmatch_worker/exports/excel.py` (`build_excel_workbook`, line 105), `ws.auto_filter.ref` is unconditionally set to `f"A1:{get_column_letter(_URL_COLUMN)}{len(rows) + 1}"`. When `rows` is empty (`len(rows) == 0`), `A1:X1` spans only the header row, which triggers an Excel repair warning.
- **Solution**:
  - In `apps/worker/jobmatch_worker/exports/service.py` (`_upload_report`), pass `headers={"Content-Type": "application/octet-stream", "x-upsert": "true"}`.
  - In `apps/worker/jobmatch_worker/exports/pdf.py` (`_link`), escape quotes via `escape(url, {'"': "&quot;", "'": "&#39;"})`.
  - In `apps/worker/jobmatch_worker/exports/excel.py` (`build_excel_workbook`), guard `ws.auto_filter.ref` with `if rows:`.
  - Add regression tests in `apps/worker/tests/test_pdf_export.py` (URL containing double quotes) and `apps/worker/tests/test_excel_export.py` (empty `rows` leaves `ws.auto_filter.ref` unset).

### 4. Fix Pinned HTTPS Transport Hanging on Keep-Alive Responses Without Content-Length

- **Problem**:
  - In `apps/worker/jobmatch_worker/jobs/connectors/pinning_transport.py` (`_build_request_bytes`, lines 336–353), incoming `Connection` headers are stripped (`if lower in ("host", "accept-encoding", "connection", "content-length"): continue`), and no `Connection: close` header is emitted.
  - Because `PinnedHttpsTransport` opens a fresh socket per request and `_ResponseStream` reads until EOF when a response lacks `Content-Length` and `Transfer-Encoding: chunked`, HTTP/1.1 servers that default to keep-alive hold the socket open until the 10s read timeout expires (`SourceUnavailable`).
- **Solution**:
  - In `apps/worker/jobmatch_worker/jobs/connectors/pinning_transport.py` (`_build_request_bytes`, line 349), append `headers.append("Connection: close")` immediately after `headers.append("Accept-Encoding: identity")`.
  - Add a unit assertion in `apps/worker/tests/test_job_connectors.py` verifying `_build_request_bytes` includes `Connection: close\r\n`.

### 5. Fix `MatchTable` Status Filtering, Default Sort Status Mapping, and `removeJob` Error Rollback

- **Problem**:
  - In `apps/web/components/jobs/match-table.tsx` (lines 66–79), `applyMatchFilters(rows, filters)` runs on the raw `rows` prop before applying optimistic `statuses[row.jobId]`. If a user saves or unsaves a job in the table and then filters by `Status` (e.g., `saved`), `applyMatchFilters` checks the stale initial `row.status` instead of `statuses[row.jobId]`. Additionally, the default sort branch (`if (sort.key === "overallScore" && sort.direction === "desc") return sortMatchesDefault(filtered);`) returns rows with stale `row.status`.
  - In `removeJob` (`apps/web/components/jobs/match-table.tsx`, lines 111–127), `removedJobIds` is updated optimistically before `fetch("/api/job-status?...", { method: "DELETE" })`, but if the response is `!response.ok` or throws a network error, `removedJobIds` is never rolled back.
- **Solution**:
  - In `apps/web/components/jobs/match-table.tsx`, compute `rowsWithCurrentStatus` first inside `useMemo`, then filter and sort:
    ```typescript
    const visibleRows = useMemo(() => {
      const currentRows = rows
        .filter((row) => !removedJobIds.has(row.jobId))
        .map((row) => ({ ...row, status: statuses[row.jobId] ?? row.status }));
      const filtered = applyMatchFilters(currentRows, filters).filter((row) => {
        if (filters.status === "all" && row.status === "ignored") return false;
        return true;
      });
      if (sort.key === "overallScore" && sort.direction === "desc") {
        return sortMatchesDefault(filtered);
      }
      return filtered.sort((a, b) => compareRows(a, b, sort));
    }, [rows, filters, sort, statuses, removedJobIds]);
    ```
  - In `removeJob` (`apps/web/components/jobs/match-table.tsx`, lines 111–127), roll back `removedJobIds` when `!response.ok` or on `catch`:
    ```typescript
    async function removeJob(jobId: string) {
      setRemovedJobIds((prev) => {
        const next = new Set(prev);
        next.add(jobId);
        return next;
      });
      setSaving((current) => ({ ...current, [jobId]: true }));
      try {
        const response = await fetch(`/api/job-status?job_id=${encodeURIComponent(jobId)}`, {
          method: "DELETE",
        });
        if (!response.ok) {
          setRemovedJobIds((prev) => {
            const next = new Set(prev);
            next.delete(jobId);
            return next;
          });
        }
      } catch {
        setRemovedJobIds((prev) => {
          const next = new Set(prev);
          next.delete(jobId);
          return next;
        });
      } finally {
        setSaving((current) => ({ ...current, [jobId]: false }));
      }
    }
    ```
  - Add unit tests in `apps/web/tests/match-table.test.tsx` verifying status filtering after clicking `Save` and rollback when `DELETE /api/job-status` fails.

### 6. Fix `DELETE /api/job-status` Error Handling, `POST /api/job-status` `updated_at` Freshness, `POST /api/exports` Date Filter Schema, and `POST /api/locale` Cookie Sync

- **Problem**:
  - **`DELETE /api/job-status` Swallows DB Errors**: `apps/web/app/api/job-status/route.ts` (lines 87–92) runs `Promise.all` on `job_matches` and `user_jobs` deletes without checking `.error`, returning `200 { deleted: true }` even when deletion fails.
  - **`POST /api/job-status` Leaves `updated_at` Stale**: `apps/web/app/api/job-status/route.ts` (lines 44–54) upserts `public.user_jobs` without `updated_at`. Because `public.user_jobs` has no `BEFORE UPDATE` trigger, status updates keep the original creation timestamp and break activity ordering on `/dashboard/tracker`.
  - **`POST /api/exports` Rejects `YYYY-MM-DD` Date Filters**: `apps/web/app/api/exports/route.ts` (lines 16–17) validates `date_from` and `date_to` with `z.string().datetime()`, rejecting the `YYYY-MM-DD` strings produced by `apps/web/lib/jobs/filter.ts` and expected by `apps/worker/jobmatch_worker/exports/models.py` (`date`).
  - **`POST /api/locale` Omits Response Cookie**: `apps/web/app/api/locale/route.ts` (lines 29–38) updates `public.profiles.locale` but does not set the `locale` cookie on the HTTP response read by `apps/web/i18n/request.ts`.
- **Solution**:
  - In `apps/web/app/api/job-status/route.ts`:
    - Add `updated_at: new Date().toISOString()` to the `user_jobs` upsert object in `POST` (line 51).
    - In `DELETE` (lines 87–92), inspect `const [matchesDelete, userJobsDelete] = await Promise.all(...)` and if `matchesDelete.error || userJobsDelete.error`, return `NextResponse.json({ error: "delete_failed" }, { status: 500 })`.
  - In `apps/web/app/api/exports/route.ts` (lines 16–17), update `date_from` and `date_to` in `exportFiltersSchema` to `z.union([z.string().date(), z.string().datetime()]).optional()`.
  - In `apps/web/app/api/locale/route.ts` (line 38), set the `locale` cookie on the returned `NextResponse`:
    ```typescript
    const response = NextResponse.json({ locale: body.locale });
    response.cookies.set("locale", body.locale, {
      path: "/",
      maxAge: 31536000,
      sameSite: "lax",
    });
    return response;
    ```
  - Add unit tests in `apps/web/tests/job-status.test.ts`, `apps/web/tests/export-request.test.ts`, and `apps/web/tests/locale.test.ts`.

### 7. Fix Database Foreign Key Cascade and Infrastructure/Test Scripts

- **Problem**:
  - **Missing `ON DELETE CASCADE` on `job_matches.candidate_profile_id`**: In `supabase/migrations/202608160006_matching.sql:15`, `candidate_profile_id uuid not null references public.candidate_profiles(id)` lacks `on delete cascade`, causing direct profile or CV deletions outside the custom RPC to fail with PostgreSQL error `23503`.
  - **Broken `scripts/test-db.cmd`**: Line 13 invokes `supabase db test "%TEST_FILE%"` (invalid Supabase CLI subcommand; the valid command is `supabase test db`) and never checks `%ERRORLEVEL%`, causing `findstr` to miss pgTAP failure strings and exit `0` on every CLI error.
  - **Missing `--no-dev` in `docker-compose.yml` & `scripts/production-smoke.sh`, and Unchecked 9Router Status**: `docker-compose.yml:7` and `scripts/production-smoke.sh:16` run `uv run python` without `--no-dev` in an image built with `uv sync --frozen --no-dev`. Additionally, `scripts/production-smoke.sh:40-44` prints the HTTP status code when `SMOKE_LIVE_AI_CHECKS=1` without failing on non-`200`.
- **Solution**:
  - Create append-only migration `supabase/migrations/202609120001_job_matches_cascade.sql`:
    ```sql
    alter table public.job_matches
      drop constraint job_matches_candidate_profile_id_fkey,
      add constraint job_matches_candidate_profile_id_fkey
        foreign key (candidate_profile_id)
        references public.candidate_profiles(id)
        on delete cascade;
    ```
  - In `scripts/test-db.cmd` (lines 13–19), replace `supabase db test` with `supabase test db` and check `ERRORLEVEL` before running `findstr`:
    ```bat
    supabase test db "%TEST_FILE%" > "%OUT_FILE%" 2>&1
    set "TEST_EXIT=%ERRORLEVEL%"
    type "%OUT_FILE%"
    if not "%TEST_EXIT%"=="0" (
      del /Q "%OUT_FILE%" >nul 2>&1
      exit /b %TEST_EXIT%
    )
    ```
  - In `docker-compose.yml:7`, change `command` to `["uv", "run", "--no-dev", "python", "-m", "jobmatch_worker.main"]`.
  - In `scripts/production-smoke.sh`, use `uv run --no-dev python -` on line 16, and after line 44 add:
    ```bash
    if [ "$code" != "200" ]; then
      echo "FAIL: 9Router health check returned HTTP $code"
      exit 1
    fi
    ```

## Critical files & anchors

- `apps/worker/jobmatch_worker/handlers/matching.py` (`handle_extract_job_requirements` lines 247–254, `handle_match_job` lines 336–343) — Prevents premature `job_search_runs` completion while failed match/requirement items are still queued for retry.
- `apps/worker/jobmatch_worker/main.py` (`handle_extract_cv` lines 120–139) — Ensures Supabase Storage deletion errors are raised before clearing `storage_path` and avoids retrying non-recoverable `ValueError` on unreadable DOCX files.
- `apps/web/components/jobs/match-table.tsx` (`visibleRows` lines 66–79, `removeJob` lines 111–127) — Applies optimistic status updates before filtering/sorting and rolls back `removedJobIds` when `DELETE /api/job-status` fails.
- `apps/web/app/api/job-status/route.ts` (`POST` lines 44–54, `DELETE` lines 87–92) — Refreshes `user_jobs.updated_at` on upsert and checks Supabase errors on delete.
- `apps/web/app/api/exports/route.ts` (`exportFiltersSchema` lines 10–19) — Accepts `YYYY-MM-DD` date strings from match filters alongside ISO datetimes.

## Verification

1. **Worker Unit & Regression Suite**:
   - Run from repository root:
     ```bash
     cd apps/worker && uv run ruff check . && uv run mypy jobmatch_worker && uv run pytest -q
     ```
   - New-behavior proofs:
     - `test_match_job_handler_retry_does_not_complete_run`: `handle_match_job` with `_FailingRouter` (`RetryableAiError`) on `attempts=1` and `pending=0` requeues the work item without updating `public.job_search_runs`.
     - `test_extracts_text_from_table_only_docx`: `extract_cv_text` extracts ≥80 chars from a DOCX whose text lives entirely inside `doc.tables`.
     - `test_pdf_escapes_double_quotes_in_job_url`: `build_pdf_bytes` succeeds when `original_url` contains `"` (`https://example.com/jobs?q="engineer"`).
     - `test_empty_rows_omits_invalid_autofilter`: `build_excel_workbook([], make_candidate(), make_criteria())` leaves `ws.auto_filter.ref` as `None`.
2. **Web Lint, Typecheck & Vitest Suite**:
   - Run from repository root:
     ```bash
     pnpm --dir apps/web lint && pnpm --dir apps/web typecheck && pnpm --dir apps/web test
     ```
   - New-behavior proofs:
     - `MatchTable`: clicking `Save` on a `"new"` row and selecting the `"saved"` status filter keeps the row visible; a `500` response from `DELETE /api/job-status` restores the row to the table.
     - `POST /api/exports`: accepts `filters: { date_from: "2026-09-01", date_to: "2026-09-30" }` with status `202`.
     - `DELETE /api/job-status`: returns `500 { error: "delete_failed" }` when Supabase delete returns an error.
     - `POST /api/locale`: returns `Set-Cookie` header containing `locale=en`.
3. **Full Workspace Check & Whitespace Audit**:
   - Run from repository root:
     ```bash
     pnpm check && git diff --check
     ```

## Assumptions & contingencies

- **Export `"best_and_strong"` threshold**: `apps/worker/jobmatch_worker/exports/service.py` (`_SCOPE_BEST_MIN_SCORE = 80`) and `apps/worker/jobmatch_worker/exports/pdf.py` (`80 <= r.overall_score < 90`) are intentionally preserved at `80` because `apps/worker/tests/test_export_service.py` and `apps/worker/tests/test_pdf_export.py` explicitly assert the `80` cutoff. If product requirements later change export thresholds to match the web UI's `71` strong bucket cutoff, update `_SCOPE_BEST_MIN_SCORE`, `pdf.py:157`, and both worker test files together.
- **Dashboard cumulative match query**: `apps/web/app/dashboard/page.tsx` queries `job_matches` by `user_id` and deduplicates by `job_id` across runs as introduced in commit `f0a7ce1`; this behavior is preserved.
